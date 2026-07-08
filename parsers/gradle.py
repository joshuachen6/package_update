from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from ado.extractor import (
    build_fuzzy_patterns,
    build_package_patterns,
    read_csv_full_rows,
)
from shared.cache import cache_by_requests_transport
from shared.maven_version import MAVEN_VERSION_RE, MavenVersion
from shared.utils import ProgressBar
from shared.xray import filter_versions_without_cves

DEPENDENCY_PATTERN = re.compile(
    r"""(?P<config>implementation|api|compileOnly|runtimeOnly|annotationProcessor
                  |testImplementation|testRuntimeOnly|testCompileOnly)\s+
        ['"](?P<group>[^:'"]+):(?P<artifact>[^:'"]+):(?P<version>[^'"]+)['"]""",
    re.VERBOSE,
)

_FUZZY_STOPWORDS: frozenset = frozenset(
    {
        "apache",
        "google",
        "amazon",
        "eclipse",
        "sonatype",
        "embed",
        "extra",
        "build",
        "utils",
        "tools",
        "model",
        "types",
        "proxy",
        "plugin",
        "starter",
        "support",
        "client",
        "server",
        "service",
        "platform",
        "framework",
        "javax",
        "jakarta",
        "compile",
        "runtime",
    }
)


@dataclass
class GradleDep:
    config: str
    group: str
    artifact: str
    version: str
    original: str
    match_start: int
    match_end: int


def _fuzzy_keywords(name: str) -> list[str]:
    """Splits an artifact or group:artifact name into significant keywords for fuzzy ADO text matching."""
    parts = re.split(r"[-._:]", name.lower())
    return list({p for p in parts if len(p) >= 5 and p not in _FUZZY_STOPWORDS and not p.isdigit()})


_JAVA_FQCN_RE = re.compile(
    r"\b(?:[a-z_][a-z0-9_]*\.){2,}[A-Z][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?\b"
)

_IN_LIBRARY_RE = re.compile(
    r"\bin\s+([A-Za-z0-9_.-]+)(?:\s+(?:before|prior\s+to|versions?|package|library|module)\b|[\s,.;)])",
    re.IGNORECASE,
)


def _artifact_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _java_advisory_candidates(text: str, known_packages: set[str]) -> set:
    """Return strong Gradle candidate hints from Java class/library advisory text.
    This is intentionally conservative: it only creates Claude hints. It does
    not commit package/version mappings directly.
    """
    if not text:
        return set()

    by_artifact: dict[str, set[str]] = {}
    by_group: dict[str, set[str]] = {}
    artifact_aliases: dict[str, set[str]] = {}

    for pkg in known_packages:
        if ":" not in pkg:
            continue
        group, artifact = pkg.split(":", 1)
        by_artifact.setdefault(artifact.lower(), set()).add(pkg)
        by_group.setdefault(group.lower(), set()).add(pkg)
        artifact_aliases.setdefault(_artifact_alias(artifact), set()).add(pkg)
    candidates: set[str] = set()
    explicit_artifacts: list[str] = []

    # Explicit artifact/library names, e.g. "in plexus-utils before ..."
    for m in _IN_LIBRARY_RE.finditer(text):
        raw = m.group(1).strip(". ,;:()[]{}")
        alias = _artifact_alias(raw)
        if alias:
            explicit_artifacts.append(alias)
        candidates.update(artifact_aliases.get(alias, set()))
        candidates.update(by_artifact.get(raw.lower(), set()))

    # Fully qualified Java classes, e.g. org.codehaus.plexus.util.Expand.
    # Map longest matching Maven group prefix first, then fall back to artifact
    # tokens in the class/package name.
    for m in _JAVA_FQCN_RE.finditer(text):
        fqcn = m.group(0).lower()
        parts = fqcn.split(".")
        package_parts = parts[:-1]
        for i in range(len(package_parts), 1, -1):
            group = ".".join(package_parts[:i])
            if group in by_group:
                candidates.update(by_group[group])
                break

        tokens = set(package_parts)
        for artifact, pkgs in by_artifact.items():
            artifact_tokens = {t for t in re.split(r"[-._]+", artifact.lower()) if t}
            if artifact_tokens and artifact_tokens.issubset(tokens):
                candidates.update(pkgs)

        # If advisory lookup failed and the dependency is not already in the
        # tree, synthesize a high-confidence Maven coordinate from explicit
        # artifact text plus the Java package namespace. Example:
        # org.codehaus.plexus.util.Expand in plexus-utils
        # becomes org.codehaus.plexus:plexus-utils.
        # This remains only a Claude hint; it is not committed unless Claude
        # returns it, and apply_updates will still skip it if absent from
        # build.gradle/dependency tree.
        for artifact_alias in explicit_artifacts:
            artifact_tokens = [t for t in artifact_alias.split("-") if t]
            if not artifact_tokens:
                continue
            anchor = artifact_tokens[0]
            if anchor not in package_parts:
                continue
            anchor_idx = package_parts.index(anchor)
            if anchor_idx < 1:
                continue
            group = ".".join(package_parts[: anchor_idx + 1])
            candidates.add(f"{group}:{artifact_alias}")

    return candidates


_STRICT_DEP_HEADER_RE = re.compile(
    r"\b(implementation|api|compileOnly|runtimeOnly|annotationProcessor|testImplementation|testRuntimeOnly|testCompileOnly)\s*\(([^)]*)\)\s*\{",
    re.DOTALL,
)

_STRICT_STRING_DEP_HEADER_RE = re.compile(
    r"\b(implementation|api|compileOnly|runtimeOnly|annotationProcessor|testImplementation|testRuntimeOnly|testCompileOnly)\s*\(\s*(['\"])([^:'\"]+):([^:'\"]+)\2\s*\)\s*\{",
    re.DOTALL,
)


def _extract_gradle_attr(attrs, name):
    m = re.search(r"\b" + re.escape(name) + r"\s*:\s*(['\"])(.*?)\1", attrs)
    return m.group(2) if m else None


def _extract_strict_version(block):
    m = re.search(r"\bstrictly\s+(['\"])(.*?)\1", block)
    return m.group(2) if m else None


def _find_matching_brace(text, open_idx):
    depth = 0
    for idx in range(open_idx, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return idx
    return -1


def parse_gradle_deps(build_text):
    deps = []

    for m in DEPENDENCY_PATTERN.finditer(build_text):
        deps.append(
            GradleDep(
                config=m.group("config"),
                group=m.group("group"),
                artifact=m.group("artifact"),
                version=m.group("version"),
                original=m.group(0),
                match_start=m.start(),
                match_end=m.end(),
            )
        )

    for m in _STRICT_DEP_HEADER_RE.finditer(build_text):
        config = m.group(1)
        attrs = m.group(2)

        group = _extract_gradle_attr(attrs, "group")
        artifact = _extract_gradle_attr(attrs, "name")
        if not group or not artifact:
            continue

        open_idx = build_text.find("{", m.start(), m.end())
        if open_idx < 0:
            continue

        close_idx = _find_matching_brace(build_text, open_idx)
        if close_idx < 0:
            continue

        original = build_text[m.start() : close_idx + 1]
        version = _extract_strict_version(original)
        if not version:
            continue

        deps.append(
            GradleDep(
                config=config,
                group=group,
                artifact=artifact,
                version=version,
                original=original,
                match_start=m.start(),
                match_end=close_idx + 1,
            )
        )

    for m in _STRICT_STRING_DEP_HEADER_RE.finditer(build_text):
        config = m.group(1)
        group = m.group(3)
        artifact = m.group(4)
        open_idx = build_text.find("{", m.start(), m.end())
        if open_idx < 0:
            continue
        close_idx = _find_matching_brace(build_text, open_idx)
        if close_idx < 0:
            continue
        original = build_text[m.start() : close_idx + 1]
        version = _extract_strict_version(original)
        if not version:
            continue
        deps.append(
            GradleDep(
                config=config,
                group=group,
                artifact=artifact,
                version=version,
                original=original,
                match_start=m.start(),
                match_end=close_idx + 1,
            )
        )

    return sorted(deps, key=lambda d: d.match_start)


def collect_known_packages(
    deps: list[GradleDep],
    dep_tree_installed: dict | None = None,
) -> set[str]:
    """Returns artifact names and group:artifact strings for ADO matching.

    If dep_tree_installed is provided (from parse_gradle_dep_tree), transitive
    dep keys are included so Claude can match CVE tasks that mention them.
    """
    known: set[str] = set()
    for dep in deps:
        known.add(dep.artifact)
        known.add(f"{dep.group}:{dep.artifact}")
    if dep_tree_installed:
        for key in dep_tree_installed:
            known.add(key)
            artifact = key.split(":", 1)[-1] if ":" in key else key
            known.add(artifact)
    return known


@cache_by_requests_transport
def get_available_versions(
    group: str,
    artifact: str,
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
) -> tuple[list[MavenVersion], str]:
    import requests

    group_path = group.replace(".", "/")
    url = f"{base_url}/{group_path}/{artifact}/maven-metadata.xml"
    try:
        resp = requests.get(url, auth=auth, timeout=timeout)
    except Exception as exc:
        return [], f"request failed: {exc}"
    if resp.status_code != 200:
        return [], f"HTTP {resp.status_code} for {url}"
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        return [], f"XML parse error: {exc}"
    versions = []
    for node in root.findall(".//version"):
        raw = (node.text or "").strip()
        v = MavenVersion.parse(raw)
        if v:
            versions.append(v)
    return sorted(versions), ""


@cache_by_requests_transport
def version_accessible(
    group: str,
    artifact: str,
    version: str,
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
) -> bool:
    import requests

    group_path = group.replace(".", "/")
    url = f"{base_url}/{group_path}/{artifact}/{version}/{artifact}-{version}.jar"
    try:
        resp = requests.head(url, auth=auth, allow_redirects=True, timeout=timeout)
    except Exception:
        return False
    return resp.status_code == 200


def parallel_fetch_versions(
    deps: list[GradleDep],
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
    workers: int,
    show_progress: bool,
) -> tuple[dict[str, list[MavenVersion]], list[dict]]:
    results: dict[str, list[MavenVersion]] = {}
    errors: list[dict] = []

    # Maven metadata lookup is keyed by group:artifact. Duplicate dependency
    # declarations or repeated strict/version blocks should not trigger
    # duplicate network calls during the same fetch phase.
    unique_deps: dict[str, GradleDep] = {}
    for dep in deps:
        unique_deps.setdefault(f"{dep.group}:{dep.artifact}", dep)

    progress = ProgressBar(
        len(unique_deps),
        f"Fetching Artifactory versions ({workers} workers)",
        enabled=show_progress,
    )

    def fetch(dep: GradleDep) -> tuple[str, list[MavenVersion], str]:
        key = f"{dep.group}:{dep.artifact}"
        versions, error = get_available_versions(dep.group, dep.artifact, base_url, auth, timeout)
        return key, versions, error

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch, dep): key for key, dep in unique_deps.items()}
        for future in as_completed(futures):
            key, versions, error = future.result()
            progress.update()
            results[key] = versions
            if error:
                errors.append({"dependency": key, "error": error})
    return results, errors


def find_accessible_version(
    group: str,
    artifact: str,
    start: MavenVersion,
    available: list[MavenVersion],
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
    xray_host: str | None = None,
) -> str | None:
    """Return a non-vulnerable accessible same-major Maven version.

    Prefer the normal forward path first: same-major versions at or above the
    selected target, ordered from nearest to highest. If Xray filtering and
    Artifactory accessibility checks leave no usable forward candidate, fall
    back to lower same-major versions from nearest to oldest. The caller's build
    validation is still responsible for proving a lower fallback compiles before
    the written update is kept.
    """

    package = f"{group}:{artifact}"
    forward_candidates = sorted(
        v for v in available if v.major == start.major and v >= start
    )
    backward_candidates = sorted(
        (v for v in available if v.major == start.major and v < start),
        reverse=True,
    )

    forward_candidates, _forward_cves, _forward_xray_error = filter_versions_without_cves(
        "maven",
        package,
        forward_candidates,
        xray_host=xray_host,
        auth=auth,
        timeout=timeout,
    )
    backward_candidates, _backward_cves, _backward_xray_error = filter_versions_without_cves(
        "maven",
        package,
        backward_candidates,
        xray_host=xray_host,
        auth=auth,
        timeout=timeout,
    )

    for candidate in forward_candidates:
        if version_accessible(group, artifact, str(candidate), base_url, auth, timeout):
            return str(candidate)

    for candidate in backward_candidates:
        if version_accessible(group, artifact, str(candidate), base_url, auth, timeout):
            return str(candidate)

    return None


def extract_ado_versions(
    csv_path: str,
    columns: list[str] | None,
    known_packages: set[str],
    show_progress: bool,
    claude_model: str = "haiku",
    claude_effort: str = "low",
    claude_timeout: int = 120,
    claude_workers: int = 4,
    claude_cmd: str = "claude",
    claude_batch_size: int = 40,
) -> tuple[dict[str, set[MavenVersion]], dict[str, set[int]], dict[str, str], set[str]]:
    """
    Returns (package_versions, package_task_ids, package_constraints, osv_packages).
    package_versions: {package_key: {MavenVersion, ...}}
    package_task_ids: {package_key: {task_id, ...}}
    package_constraints: {package_key: ">=" | ">"}
    Every row with version numbers is sent to Claude in batched prompts;
    pattern matching provides candidates as hints.
    """
    rows = read_csv_full_rows(csv_path, columns)
    pkg_patterns = build_package_patterns(known_packages)
    fuzzy_patterns = build_fuzzy_patterns(known_packages, _FUZZY_STOPWORDS)
    progress = ProgressBar(len(rows), "Extracting ADO package/version pairs", enabled=show_progress)
    package_versions: dict[str, set[MavenVersion]] = {}
    package_task_ids: dict[str, set[int]] = {}
    package_constraints: dict[str, str] = {}
    pending: list[tuple[int | None, str, list[str], set[MavenVersion]]] = []

    def _commit(task_id: int | None, pkg_map: dict[str, str], versions: set[MavenVersion]) -> None:
        for pkg, constraint in pkg_map.items():
            for v in versions:
                package_versions.setdefault(pkg, set()).add(v)
            if task_id is not None:
                package_task_ids.setdefault(pkg, set()).add(task_id)
            # ">" is more restrictive; keep it once seen
            if package_constraints.get(pkg) != ">":
                package_constraints[pkg] = constraint

    # CVE/GHSA pre-pass: look up canonical package names + fixed versions from OSV.
    # Tasks resolved this way skip the NLP/Claude path entirely.
    from shared.cve_lookup import extract_advisory_id, prefetch_advisories

    _advisory_cache = prefetch_advisories(rows, "Maven")
    handled_task_ids: set[int | None] = set()
    osv_packages: set[str] = set()  # packages identified via OSV/NVD (not NLP)

    for task_id, title, _text in rows:
        aid = extract_advisory_id(title)
        if not aid or aid not in _advisory_cache:
            continue
        pkg_fixed = _advisory_cache[aid]
        if not pkg_fixed:
            continue
        for pkg_name, fixed_strs in pkg_fixed.items():
            for fixed_str in fixed_strs:
                v = MavenVersion.parse(fixed_str)
                if v:
                    package_versions.setdefault(pkg_name, set()).add(v)
            if task_id is not None:
                package_task_ids.setdefault(pkg_name, set()).add(task_id)
            if package_constraints.get(pkg_name) != ">":
                package_constraints[pkg_name] = ">="
            osv_packages.add(pkg_name)
        # Only skip NLP if at least one resolved name is a known package.
        # If none match (e.g. NVD product name differs from Maven coordinate),
        # let NLP run to find the correct name.
        if any(p in known_packages for p in pkg_fixed):
            handled_task_ids.add(task_id)

    for task_id, _title, text in rows:
        if task_id in handled_task_ids:
            progress.update()
            continue
        progress.update()
        if not text.strip():
            continue

        row_versions: set[MavenVersion] = set()
        for m in MAVEN_VERSION_RE.finditer(text):
            v = MavenVersion.parse(m.group(1))
            if v:
                row_versions.add(v)

        candidates = [
            pkg
            for pkg, pattern in pkg_patterns.items()
            if pattern.search(text)
            or (pkg in fuzzy_patterns and any(fp.search(text) for fp in fuzzy_patterns[pkg]))
        ]
        java_candidates = _java_advisory_candidates(text, known_packages)
        if java_candidates:
            candidates = sorted(set(candidates) | java_candidates)

        # Some ADO CVE tasks name an affected framework/package but omit the fixed
        # version. Still send those rows to Claude when dependency-tree candidates
        # exist; apply_updates can then use same-major Artifactory/JFrog fallback
        # for packages Claude identifies. Rows with neither versions nor
        # candidates remain unhelpful and are skipped.
        if not row_versions and not candidates:
            continue

        # Regex/fuzzy matches are only candidate hints for Claude. They must not
        # create final package/version mappings by themselves. Claude is the
        # authority for NLP extraction; OSV/NVD advisory lookup above remains the
        # deterministic path for canonical vulnerability data.
        pending.append((task_id, text, candidates, row_versions))

    if pending:
        from resolver.claude_resolver import batch_resolve

        def _with_candidate_hints(text: str, candidates: list[str]) -> str:
            if not candidates:
                return text
            candidate_set = set(candidates)
            full_artifacts = {pkg.split(":")[-1] for pkg in candidate_set if ":" in pkg}
            preferred = sorted(
                pkg for pkg in candidate_set if ":" in pkg or pkg not in full_artifacts
            )
            if not preferred:
                return text
            hints = "\n".join(f"- {pkg}" for pkg in preferred)
            return (
                f"{text}\n\n"
                "Candidate package hints from exact/fuzzy matching. "
                "Use these only if the task actually discusses that package; "
                "do not return a package solely because it appears in this hint list.\n"
                f"{hints}"
            )

        claude_tasks = [(tid, _with_candidate_hints(txt, cands)) for tid, txt, cands, _ in pending]
        claude_known_packages = set(known_packages)
        for _, _, cands, _ in pending:
            claude_known_packages.update(cands)
        resolved_by_idx, _ = batch_resolve(
            claude_tasks,
            claude_known_packages,
            model=claude_model,
            effort=claude_effort,
            timeout=claude_timeout,
            workers=claude_workers,
            claude_cmd=claude_cmd,
            batch_size=claude_batch_size,
            allow_unlisted=False,
        )
        for i, (task_id, _, _, row_versions) in enumerate(pending):
            _commit(task_id, resolved_by_idx.get(i, {}), row_versions)

    return package_versions, package_task_ids, package_constraints, osv_packages
