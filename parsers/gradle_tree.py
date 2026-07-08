from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

from shared.cache import cache_by_subprocess_run
from shared.maven_version import MavenVersion

# Matches the dep declaration in a Gradle dependency tree line, e.g.:
#   com.example:foo:1.2.3
#   com.example:foo:1.2.3 -> 2.0.0
#   com.example:foo:1.2.3 -> 2.0.0 (*)
#   com.example:foo -> 2.0.0
_DEP_LINE_RE = re.compile(r"([\w.-]+):([\w.-]+)(?::([\w.+-]+))?(?:\s+->\s+([\w.+-]+))?")


def get_gradle_cmd(project_dir: str) -> str:
    gradlew = os.path.join(project_dir, "gradlew")
    if os.path.isfile(gradlew) and os.access(gradlew, os.X_OK):
        return gradlew
    return "gradle"


def run_gradle_dependencies(
    project_dir: str,
    gradle_cmd: str,
    timeout: int,
    configuration: str = "runtimeClasspath",
) -> tuple[str | None, str | None]:
    """Returns (stdout, error_message). On success error_message is None."""
    cmd = [
        gradle_cmd,
        "dependencies",
        f"--configuration={configuration}",
        "--no-daemon",
        "--console=plain",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_dir,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    except FileNotFoundError:
        return None, f"command not found: {gradle_cmd!r}"
    except Exception as exc:
        return None, str(exc)

    stdout = result.stdout or ""
    stderr = (result.stderr or "").strip()
    # Only treat stdout as a valid tree if it actually contains tree lines
    has_tree = "+---" in stdout or "\\---" in stdout
    tree_out = stdout if has_tree else None

    if result.returncode != 0:
        msg = f"exit code {result.returncode}"
        if stderr:
            msg = f"{msg}\n{stderr}"
        return tree_out, msg
    return tree_out, None


def parse_gradle_dep_tree(
    output: str,
) -> tuple[dict[str, MavenVersion], dict[str, set[str]]]:
    """Parse `gradle dependencies` stdout.

    Returns:
        installed  — {group:artifact: resolved_MavenVersion}
        parents_of — {transitive_g:a: {direct_parent_g:a, ...}}
    """
    installed: dict[str, MavenVersion] = {}
    parents_of: dict[str, set[str]] = {}

    # Stack entries: (depth, key)
    stack: list = []

    for raw_line in output.splitlines():
        # Skip blank lines and section headers (no "+---" or "\\---")
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip("|")
        if "+---" not in stripped and "\\---" not in stripped:
            continue

        # Gradle renders each nested level as one 5-character indent unit before
        # the dependency connector. The connector itself should not contribute to
        # the depth: top-level dependencies are depth 0, their children are depth 1,
        # and so on. Keeping that convention makes parent tracking straightforward.
        depth = 0
        i = 0
        while i < len(raw_line):
            chunk = raw_line[i : i + 5]
            if chunk == "|    " or chunk == "     ":
                depth += 1
                i += 5
            elif chunk in ("+--- ", "\\--- "):
                break
            else:
                break

        m = _DEP_LINE_RE.search(raw_line)
        if not m:
            continue

        group, artifact = m.group(1), m.group(2)
        raw_version = m.group(4) or m.group(3)  # prefer resolved (-> X) over declared
        if not raw_version:
            continue
        key = f"{group}:{artifact}"

        # Prune stack to current depth
        while stack and stack[-1][0] >= depth:
            stack.pop()

        stack.append((depth, key))

        # Skip already-resolved duplicates marked with (*) for parent tracking,
        # but still record the installed version if not yet seen.
        is_duplicate = raw_line.rstrip().endswith("(*)")
        is_failed = "FAILED" in raw_line

        if not is_failed:
            v = MavenVersion.parse(raw_version)
            if v and key not in installed:
                installed[key] = v

        if not is_duplicate and not is_failed and depth > 0:
            # Direct parent is depth-0 entry on the stack
            direct = next((k for d, k in stack if d == 0), None)
            if direct and direct != key:
                parents_of.setdefault(key, set()).add(direct)

    return installed, parents_of


@cache_by_subprocess_run
def resolve_transitive_with_gradle(
    parent_key: str,
    new_parent_version: str,
    transitive_key: str,
    project_dir: str,
    build_file: str,
    gradle_cmd: str,
    timeout: int,
    configuration: str = "runtimeClasspath",
) -> MavenVersion | None:
    """Simulate updating parent_key to new_parent_version and return the resolved
    version of transitive_key, or None if resolution fails or transitive not found."""

    build_text = _read_file(build_file)
    if build_text is None:
        return None

    parent_group, parent_artifact = parent_key.split(":", 1)
    modified = _replace_dep_version(build_text, parent_group, parent_artifact, new_parent_version)

    with tempfile.TemporaryDirectory() as tmp:
        _copy_gradle_files(project_dir, tmp)
        tmp_build = os.path.join(tmp, os.path.basename(build_file))
        try:
            with open(tmp_build, "w", encoding="utf-8") as fh:
                fh.write(modified)
        except Exception:
            return None

        cmd = [
            gradle_cmd,
            "dependencies",
            f"--configuration={configuration}",
            "--no-daemon",
            "--console=plain",
            "-q",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                shell=False,
            )
        except (subprocess.TimeoutExpired, Exception):
            return None

        if result.returncode != 0:
            return None

        simulated, _ = parse_gradle_dep_tree(result.stdout)
        return simulated.get(transitive_key)


_RESOLVE_RE = re.compile(r"Could not resolve\s+([^:\s]+):([^:\s]+):([^\s,()]+)")
_DOWNLOAD_RE = re.compile(r"Could not download [^\(]*\(([^:\s]+):([^:\s]+):([^\s,()]+)\)")
_GET_URL_RE = re.compile(r"Could not GET '(https://[^']+)'")


def _parse_blocked_packages(
    error: str,
) -> list[tuple[str, str, str, str | None]]:
    """Extract (group, artifact, version, repo_base_url) for 403-blocked packages.

    Matches both:
      - project deps:    Could not resolve group:artifact:version
      - buildscript deps: Could not download foo.jar (group:artifact:version)
    repo_base_url is derived from the 'Could not GET' URL in the same error block, or None.
    """
    lines = error.splitlines()
    blocked: list[tuple[str, str, str, str | None]] = []
    seen: set = set()

    for i, line in enumerate(lines):
        m = _RESOLVE_RE.search(line) or _DOWNLOAD_RE.search(line)
        if not m:
            continue
        version = m.group(3).rstrip(".")
        triple = (m.group(1), m.group(2), version)
        if triple in seen:
            continue
        context = "\n".join(lines[i : i + 10])
        if "403" not in context and "Forbidden" not in context:
            continue
        seen.add(triple)
        repo_url: str | None = None
        url_m = _GET_URL_RE.search(context)
        if url_m:
            full_url = url_m.group(1)
            group_path = triple[0].replace(".", "/")
            idx = full_url.find(f"/{group_path}/{triple[1]}/")
            if idx > 0:
                repo_url = full_url[:idx]
        blocked.append((*triple, repo_url))
    return blocked


def _find_block_end(text: str, open_brace: int) -> int:
    """Return the index just after the balanced block that starts at open_brace."""
    depth = 0
    quote: str | None = None
    escaped = False
    i = open_brace
    while i < len(text):
        ch = text[i]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
        else:
            if ch in ("'", '"'):
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return len(text)


def _top_level_block_end(text: str, name: str) -> int | None:
    """Find the end of the first top-level Gradle block named `name`."""
    pattern = re.compile(r"(?m)^\s*" + re.escape(name) + r"\s*\{")
    m = pattern.search(text)
    if not m:
        return None
    open_brace = text.find("{", m.start(), m.end())
    if open_brace < 0:
        return None
    return _find_block_end(text, open_brace)


def _insert_project_forces(build_text: str, proj_block: str) -> str:
    """Insert project-level forces without violating Gradle plugins {} ordering."""
    insertion_points = [
        end
        for end in (
            _top_level_block_end(build_text, "plugins"),
            _top_level_block_end(build_text, "buildscript"),
        )
        if end is not None
    ]
    if insertion_points:
        insert_at = max(insertion_points)
        spacer = "\n\n" if not build_text[insert_at:].startswith("\n") else "\n"
        return build_text[:insert_at] + spacer + proj_block + build_text[insert_at:]
    return proj_block + build_text


def _inject_forces(build_text: str, forces: dict[str, str]) -> str:
    """Inject resolutionStrategy.force entries for both project and buildscript configs."""
    if not forces:
        return build_text

    proj_lines = "\n".join(f"        force '{k}:{v}'" for k, v in forces.items())
    bs_lines = "\n".join(f"            force '{k}:{v}'" for k, v in forces.items())

    # Inject inside buildscript { } for classpath/plugin dependencies.
    bs_snippet = (
        "\n    configurations.all {\n"
        "        resolutionStrategy {\n"
        f"{bs_lines}\n"
        "        }\n"
        "    }\n"
    )
    m_bs = re.search(r"buildscript\s*\{", build_text)
    if m_bs:
        build_text = build_text[: m_bs.end()] + bs_snippet + build_text[m_bs.end() :]

    # Project-level configurations cannot be prepended before plugins {}.
    # Gradle only allows buildscript/pluginManagement/plugins-related blocks before
    # plugins {}, so insert after plugins/buildscript when they exist.
    proj_block = f"configurations.all {{\n    resolutionStrategy {{\n{proj_lines}\n    }}\n}}\n\n"
    return _insert_project_forces(build_text, proj_block)


_MAX_FALLBACK_ROUNDS = 10


def run_gradle_dependencies_with_fallback(
    project_dir: str,
    build_file: str,
    deps: list,
    available_by_key: dict[str, list[MavenVersion]],
    base_url: str,
    auth,
    gradle_cmd: str,
    timeout: int,
    configuration: str = "runtimeClasspath",
) -> tuple[str | None, str | None, dict[str, str]]:
    """Run gradle dependencies, unblocking 403'd packages by forcing accessible versions.

    For each blocked package an accessible alternative version is found (same-major up,
    same-major down, other-major) and applied via resolutionStrategy.force.  Packages
    with no accessible version at all are logged and skipped — their declarations are
    left untouched.  If after forcing all resolvable packages Gradle still cannot
    produce a tree, the original error is returned as a fatal error.

    Loops across rounds because Gradle only reports 403s for packages it actually
    tried to fetch; transitives hidden behind a blocked parent only surface once
    that parent is unblocked.

    Returns (stdout, error_message, bumped) where bumped is {group:artifact: forced_version}.
    """
    from parsers.gradle import get_available_versions, version_accessible

    stdout, err = run_gradle_dependencies(project_dir, gradle_cmd, timeout, configuration)
    if stdout:
        return stdout, err, {}

    blocked = _parse_blocked_packages(err or "")
    if not blocked:
        print("  Gradle failed — no 403-blocked packages detected, cannot retry")
        return None, err, {}

    print(f"  Gradle failed — {len(blocked)} 403-blocked package(s) detected, entering retry loop")

    build_text = _read_file(build_file)
    if build_text is None:
        return None, err, {}

    all_bumped: dict[str, str] = {}  # key -> version forced in temp build
    all_seen: set = set()  # keys already processed
    last_err = err

    for round_num in range(1, _MAX_FALLBACK_ROUNDS + 1):
        new_bumped: dict[str, str] = {}

        new_in_round = [(g, a, v, r) for g, a, v, r in blocked if f"{g}:{a}" not in all_seen]
        if not new_in_round:
            print(f"  [retry round {round_num}] no new blocked packages — stopping")
            break

        print(
            f"  [retry round {round_num}/{_MAX_FALLBACK_ROUNDS}] {len(new_in_round)} new blocked package(s)…"
        )

        for group, artifact, version, repo_url in new_in_round:
            key = f"{group}:{artifact}"
            all_seen.add(key)
            current = MavenVersion.parse(version)
            if current is None:
                print(f"    {key}: unparseable version {version!r} — skipping")
                continue
            check_url = repo_url or base_url
            avail = available_by_key.get(key)
            if not avail:
                avail, _ = get_available_versions(group, artifact, check_url, auth, timeout)
            avail_list = avail or []
            same_up = sorted(v for v in avail_list if v.major == current.major and v > current)
            same_down = sorted(
                (v for v in avail_list if v.major == current.major and v < current),
                reverse=True,
            )
            other = sorted(
                (v for v in avail_list if v.major != current.major),
                key=lambda v: (abs(v.major - current.major), v < current),
            )
            candidates = same_up + same_down + other
            if not candidates:
                print(f"    {key}: {version} — no versions available from {check_url}, skipping")
                continue
            for candidate in candidates:
                if version_accessible(group, artifact, str(candidate), check_url, auth, timeout):
                    direction = "↑" if candidate > current else "↓"
                    new_bumped[key] = str(candidate)
                    print(f"    {key}: {version} {direction} {candidate} (forced for tree)")
                    break
            else:
                print(
                    f"    {key}: {version} — no accessible version in {len(candidates)} candidate(s), skipping"
                )

        if not new_bumped:
            print(f"  [retry round {round_num}] no packages could be unblocked — fatal error")
            break

        all_bumped.update(new_bumped)

        modified = build_text
        for dep in deps:
            key = f"{dep.group}:{dep.artifact}"
            if key in all_bumped:
                modified = _replace_dep_version(modified, dep.group, dep.artifact, all_bumped[key])
        modified = _inject_forces(modified, all_bumped)

        print(
            f"  [retry round {round_num}] retrying gradle with {len(all_bumped)} forced version(s)…"
        )

        with tempfile.TemporaryDirectory() as tmp:
            _copy_gradle_files(project_dir, tmp)
            tmp_build = os.path.join(tmp, os.path.basename(build_file))
            try:
                with open(tmp_build, "w", encoding="utf-8") as fh:
                    fh.write(modified)
            except Exception as exc:
                return None, str(exc), all_bumped

            stdout2, err2 = run_gradle_dependencies(tmp, gradle_cmd, timeout, configuration)
            last_err = err2

            if stdout2:
                print(f"  [retry round {round_num}] gradle succeeded — dependency tree resolved")
                return stdout2, err2, all_bumped

            newly_blocked = _parse_blocked_packages(err2 or "")
            print(
                f"  [retry round {round_num}] gradle still failing — {len(newly_blocked)} blocked package(s) remain"
            )
            if not newly_blocked:
                return None, err2, all_bumped
            blocked = newly_blocked

    return None, last_err, all_bumped


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_file(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def _replace_dep_version(build_text: str, group: str, artifact: str, new_version: str) -> str:
    """Replace the version of group:artifact anywhere it appears as a quoted string dep declaration."""
    pattern = re.compile(
        r"(['\"]" + re.escape(group) + r":" + re.escape(artifact) + r":)" + r"([^'\"]+)(['\"])"
    )
    return pattern.sub(lambda m: f"{m.group(1)}{new_version}{m.group(3)}", build_text)


_GRADLE_FILES = {
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
}
_GRADLE_DIRS = {"gradle"}


def _copy_gradle_files(src_dir: str, dst_dir: str) -> None:
    for name in _GRADLE_FILES:
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, name))
    for name in _GRADLE_DIRS:
        src = os.path.join(src_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst_dir, name), dirs_exist_ok=True)
    for name in ("gradlew", "gradlew.bat"):
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            dst = os.path.join(dst_dir, name)
            shutil.copy2(src, dst)
            os.chmod(dst, 0o755)
