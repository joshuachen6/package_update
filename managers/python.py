from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from managers import EcosystemUpdateResult

if TYPE_CHECKING:
    from managers import WritePlan
from registry.pypi import available_versions
from shared.semver import SemVer


@dataclass
class PythonParsed:
    file_path: str
    file_type: str
    original_text: str
    requirements: list


@dataclass
class PythonVersionSet:
    versions_by_package: dict[str, tuple[str, ...]]
    fetch_errors: list = field(default_factory=list)


def _parse_requirement_name(spec):
    raw = str(spec or "").split(";", 1)[0].strip()
    if not raw:
        return ""
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", raw)
    return match.group(1).strip() if match else ""


def _load_installed_packages(python_cmd, timeout):
    proc = subprocess.run(
        [python_cmd, "-m", "pip", "inspect", "--local"],
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    payload = json.loads(proc.stdout)
    installed = {}
    for row in payload.get("installed", []):
        metadata = row.get("metadata") if isinstance(row, dict) else None
        if not isinstance(metadata, dict):
            continue
        name = metadata.get("name")
        version = metadata.get("version")
        if not name or not version:
            continue
        from parsers.python import normalize_python_package
        installed[normalize_python_package(name)] = {
            "name": name,
            "version": version,
            "requires_dist": metadata.get("requires_dist") or [],
        }
    return installed


def _resolved_dependency_lines(requirements, installed):
    lines = []

    def walk(package_name, declared_label, indent, seen):
        from parsers.python import normalize_python_package
        normalized = normalize_python_package(package_name)
        info = installed.get(normalized)
        if info:
            label = declared_label if indent == "" else f"{info['name']}=={info['version']}"
        else:
            label = declared_label if indent == "" else package_name
        lines.append(f"{indent}+-- {label}")
        if normalized in seen or not info:
            return
        next_seen = seen | {normalized}
        for dep_spec in info.get("requires_dist", []):
            if "extra ==" in dep_spec or "extra==" in dep_spec:
                continue
            dep_name = _parse_requirement_name(dep_spec)
            if not dep_name:
                continue
            walk(dep_name, dep_spec, indent + "    ", next_seen)

    for req in requirements:
        walk(req.name, f"{req.name}{req.operator}{req.version}", "", set())
    return lines


def _write_dependency_tree(path, dep_file, requirements, python_cmd, timeout):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    title = f"Python dependency tree for {dep_file}"
    lines = ["", title, "=" * len(title)]
    if not requirements:
        lines.append("(no pinned or comparable Python dependencies found)")
    else:
        try:
            installed = _load_installed_packages(python_cmd, timeout)
            lines.extend(_resolved_dependency_lines(requirements, installed))
        except Exception as exc:
            lines.append(f"(resolved tree unavailable: {exc})")
            for req in requirements:
                lines.append(f"+-- {req.name}{req.operator}{req.version}")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(chr(10).join(lines) + chr(10))


class PythonParser:
    def parse(self, file_path: str) -> PythonParsed:
        from parsers.python import dependency_file_type, parse_python_dependency_file

        file_type = dependency_file_type(file_path)
        original_text, requirements = parse_python_dependency_file(file_path)
        return PythonParsed(
            file_path=file_path,
            file_type=file_type,
            original_text=original_text,
            requirements=requirements,
        )

    def resolve_tree(self, file_path: str, parsed: PythonParsed, cfg: Any, log_dir: str) -> None:
        tree_path = Path(log_dir) / "python-dependency-tree.txt"
        _write_dependency_tree(
            tree_path, file_path, parsed.requirements, cfg.python_cmd, cfg.pip_timeout
        )
        print(f"Python dependency tree log -> {tree_path}")
        return None


class PythonRegistry:
    def fetch_versions(self, packages: list[str], cfg: Any) -> PythonVersionSet:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from parsers.python import normalize_python_package

        versions_by_package: dict[str, tuple[str, ...]] = {}
        fetch_errors: list[dict] = []
        workers = max(1, getattr(cfg, "workers", 8))

        def _fetch(pkg):
            return available_versions(pkg, cfg.python_cmd, cfg.pip_timeout, cfg.pip_index_url)

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_fetch, pkg): pkg for pkg in packages}
            for future in as_completed(futures):
                pkg = futures[future]
                try:
                    versions = future.result()
                    if versions:
                        versions_by_package[normalize_python_package(pkg)] = versions
                except Exception as exc:
                    fetch_errors.append({"package": pkg, "error": str(exc)})

        return PythonVersionSet(versions_by_package=versions_by_package, fetch_errors=fetch_errors)


class PythonOutput:
    def apply_updates(
        self,
        parsed: PythonParsed,
        tree: None,
        versions: PythonVersionSet,
        cve_packages: set[str],
        cfg: Any,
        log_dir: str | None = None,
    ) -> EcosystemUpdateResult:
        from parsers.python import normalize_python_package, update_python_dependency_text
        from shared.utils import build_display_change, build_skipped_entry

        targets = {normalize_python_package(pkg) for pkg in cve_packages}
        changes: list[dict] = []
        fetch_skipped: list[dict] = []

        xray_host = getattr(cfg, "xray_host", None)
        skip_block_check = getattr(cfg, "skip_block_check", False)

        for req in parsed.requirements:
            if not targets or req.normalized_name not in targets:
                continue
            all_versions = versions.versions_by_package.get(req.normalized_name)
            if all_versions is None:
                err = next(
                    (e["error"] for e in versions.fetch_errors if e["package"] == req.name),
                    "version not found",
                )
                fetch_skipped.append({
                    "package": req.name,
                    "current_version": req.version,
                    "reason": f"PyPI lookup failed: {err}",
                    "file": parsed.file_path,
                })
                continue

            from parsers.python import version_satisfies_constraint

            constrained_versions = tuple(
                version
                for version in all_versions
                if version_satisfies_constraint(version, req.constraint)
            )
            if not constrained_versions:
                fetch_skipped.append({
                    "package": req.name,
                    "current_version": req.version,
                    "reason": (
                        "no registry version satisfies declared constraint "
                        f"{req.constraint!r}"
                    ),
                    "file": parsed.file_path,
                })
                continue

            current_sv = SemVer.parse(req.version)
            if current_sv is None:
                candidate = constrained_versions[0]
            else:
                ascending = list(reversed(constrained_versions))
                # forward = same major, above current; backward = next major
                # up. PyPI never considers a downgrade below current, unlike
                # Maven/npm's true forward/below-current search -- find_safe_version
                # doesn't care about that distinction, it just tries the first
                # list, then the second.
                forward = [
                    v for v in ascending
                    if (sv := SemVer.parse(v))
                    and sv > current_sv
                    and sv.major == current_sv.major
                ]
                backward = [
                    v for v in ascending
                    if (sv := SemVer.parse(v))
                    and sv > current_sv
                    and sv.major > current_sv.major
                ]
                if skip_block_check:
                    candidate = next(iter(forward or backward), None)
                else:
                    from registry.pypi import is_version_blocked
                    from shared.version_search import find_safe_version

                    def _accessible(candidate_version: str, _name: str = req.name) -> bool:
                        blocked, _snippet = is_version_blocked(
                            _name,
                            candidate_version,
                            cfg.pip_index_url,
                            cfg.python_cmd,
                            cfg.pip_timeout,
                        )
                        return not blocked

                    candidate, _diagnostic = find_safe_version(
                        forward,
                        backward,
                        _accessible,
                        "pypi",
                        req.name,
                        xray_host=xray_host,
                        timeout=cfg.pip_timeout,
                    )

            if candidate is None:
                fetch_skipped.append({
                    "package": req.name,
                    "current_version": req.version,
                    "reason": "no safe version found in registry",
                    "file": parsed.file_path,
                })
                continue
            if candidate == req.version:
                continue
            changes.append({
                "package": req.name,
                "current_version": req.version,
                "new_version": candidate,
                "line_index": req.line_index,
                "change_type": "python",
                "file": parsed.file_path,
            })

        updated_text = update_python_dependency_text(
            parsed.original_text, changes, file_type=parsed.file_type
        )
        display_changes = [
            build_display_change(
                row["package"],
                row["current_version"],
                row["new_version"],
                "python",
                True,
            )
            for row in changes
        ]
        skipped_display = [
            build_skipped_entry(row["package"], row["current_version"], "", row["reason"])
            for row in fetch_skipped
        ]

        return EcosystemUpdateResult(
            display_changes=display_changes,
            skipped_display=skipped_display,
            extra={
                "original_text": parsed.original_text,
                "updated_text": updated_text,
                "requirements": parsed.requirements,
                "changes": changes,
                "skipped_raw": fetch_skipped,
                "file_type": parsed.file_type,
            },
        )

    def write_logs(self, log_dir: str, result: EcosystemUpdateResult) -> None:
        from shared.utils import write_csv_rows

        extra = result.extra
        write_csv_rows(
            str(Path(log_dir) / "python-version-changes.csv"),
            extra.get("changes", []),
            ["package", "current_version", "new_version", "change_type", "file"],
        )
        write_csv_rows(
            str(Path(log_dir) / "python-skipped.csv"),
            extra.get("skipped_raw", []),
            ["package", "current_version", "reason", "file"],
        )


class PythonManager:
    ecosystem = "pypi"
    type = "python"
    label = "Python"
    explicit_arg_attr = "python_files"
    explicit_arg_name = "--python-file"
    explicit_arg_help = "Explicit Python dependency file to update. Can be passed multiple times."
    total_keys = ("python_direct", "skipped")

    parser = PythonParser()
    registry = PythonRegistry()
    output = PythonOutput()

    def packages_to_fetch(
        self, parsed: PythonParsed, tree: None, cve_packages: set[str]
    ) -> list[str]:
        if not cve_packages:
            return []
        from parsers.python import normalize_python_package

        targets = {normalize_python_package(pkg) for pkg in cve_packages}
        return [req.name for req in parsed.requirements if req.normalized_name in targets]

    def summarize(self, result: dict) -> dict[str, int]:
        return {
            "python_direct": sum(
                1 for row in result.get("display_changes", []) if row.get("change_type") == "python"
            ),
            "skipped": len(result.get("skipped_display", [])),
        }

    def analyze(self, cfg: Any, manager: dict, log_dir: str, cve_packages: set[str]) -> dict:
        from types import SimpleNamespace

        from pipeline.runner import run_analysis

        cfg_ns = SimpleNamespace(
            python_cmd=cfg.python_cmd,
            pip_timeout=cfg.pip_timeout,
            pip_index_url=cfg.pip_index_url,
            workers=cfg.workers,
            skip_build_validation=getattr(cfg, "skip_build_validation", True),
            xray_host=getattr(cfg, "xray_host", None),
            skip_block_check=getattr(cfg, "skip_block_check", False),
        )
        return run_analysis(self, manager["file_path"], log_dir, cve_packages, cfg_ns)

    def make_write_plan(self, cfg: Any, result: dict, log_dir: str | None) -> WritePlan:
        from managers import WritePlan
        from output.python import write_python_dependency_file
        from shared.build_validation import validate_python_project_or_rollback

        path = result.get("file_path", "")
        original_text = result.get("original_text", "")
        updated_text = result.get("updated_text", "")
        changes = result.get("changes", [])
        file_type = result.get("file_type", "requirements")
        python_cmd = cfg.python_cmd
        timeout = max(cfg.pip_timeout, 600)

        return WritePlan(
            has_changes=bool(changes),
            file_path=path,
            write=lambda: write_python_dependency_file(updated_text, path, path, in_place=True),
            validate=lambda: validate_python_project_or_rollback(
                dep_file=path,
                original_text=original_text,
                python_cmd=python_cmd,
                timeout=timeout,
                changes=changes,
                log_dir=log_dir,
                file_type=file_type,
                enable_failure_isolation=getattr(cfg, "enable_failure_isolation", False),
            ),
        )

    def write_result(self, cfg: Any, result: dict, log_dir: str) -> None:
        from pipeline.runner import run_write_validate
        run_write_validate(
            self.make_write_plan(cfg, result, log_dir),
            getattr(cfg, "skip_build_validation", False),
        )
