from __future__ import annotations

import re
import time
from dataclasses import dataclass

from registry.maven import get_available_versions, version_accessible
from shared.maven_version import MavenVersion


@dataclass(frozen=True)
class GradleDep:
    config: str
    group: str
    artifact: str
    version: str
    original: str
    match_start: int
    match_end: int


DEPENDENCY_PATTERN = re.compile(
    r"""(?P<config>implementation|api|compileOnly|runtimeOnly|annotationProcessor
                  |testImplementation|testRuntimeOnly|testCompileOnly)\s+
        ['"](?P<group>[^:'"]+):(?P<artifact>[^:'"]+):(?P<version>[^'"]+)['"]""",
    re.VERBOSE,
)

DEPENDENCY_PAREN_STRING_PATTERN = re.compile(
    r"""(?P<config>implementation|api|compileOnly|runtimeOnly|annotationProcessor
                  |testImplementation|testRuntimeOnly|testCompileOnly)\s*
        \(\s*['"](?P<group>[^:'"]+):(?P<artifact>[^:'"]+):(?P<version>[^'"]+)['"]\s*\)""",
    re.VERBOSE,
)

_STRICT_DEP_HEADER_RE = re.compile(
    r"\b(implementation|api|compileOnly|runtimeOnly|annotationProcessor|testImplementation|testRuntimeOnly|testCompileOnly)\s*\(([^)]*)\)\s*\{",
    re.DOTALL,
)

_STRICT_STRING_DEP_HEADER_RE = re.compile(
    r"\b(implementation|api|compileOnly|runtimeOnly|annotationProcessor|testImplementation|testRuntimeOnly|testCompileOnly)\s*\(\s*(['\"])([^:'\"]+):([^:'\"]+)\2\s*\)\s*\{",
    re.DOTALL,
)

# ['artifact-a', 'artifact-b'].each { implementation(group: 'g', name: it) { version { strictly 'v' } } }
# -- a Groovy idiom for pinning several same-group artifacts to one shared
# version in a single block. "name: it" (the loop variable, not a literal
# string) matched none of the two header patterns above, so every artifact
# listed this way was completely invisible to parse_gradle_deps: never a
# Case 1 direct-write target, never realigned by _align_competing_pins.
# Confirmed live: cwih-cnp-mgmt-consent-api's netty-codec/netty-codec-http/
# netty-handler stayed pinned to their original strictly version -- a
# resolutionStrategy.force to the fixed version was written and reported as
# a change, but real Gradle resolution silently kept the un-rewritten
# strictly value (strictly outranks force), leaving 19 CVEs unfixed.
_EACH_LIST_HEADER_RE = re.compile(
    r"""\[\s*(?P<names>(?:['"][^'"]+['"]\s*,\s*)*['"][^'"]+['"]\s*,?\s*)\]\s*
        \.each\s*(?P<each_open>\{)\s*
        (?P<config>implementation|api|compileOnly|runtimeOnly|annotationProcessor
                  |testImplementation|testRuntimeOnly|testCompileOnly)\s*
        \(\s*group\s*:\s*(['"])(?P<group>[^'"]+)\4\s*,\s*name\s*:\s*it\s*\)\s*(?P<inner_open>\{)""",
    re.VERBOSE,
)
_QUOTED_ITEM_RE = re.compile(r"""['"]([^'"]+)['"]""")


def _extract_gradle_attr(attrs, name):
    m = re.search(r"\b" + re.escape(name) + r"\s*:\s*(['\"])(.*?)\1", attrs)
    return m.group(2) if m else None


def _extract_strict_version(block):
    m = re.search(r"\bstrictly\s*\(?\s*(['\"])(.*?)\1", block)
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


_REPOSITORIES_BLOCK_RE = re.compile(r"\brepositories\s*\{")
_MAVEN_URL_RE = re.compile(
    r"""
    url \s* = \s* uri \s* \( \s* ["']([^"'\s]+)["'] \s* \)  # url = uri("...")
    | url \s* = \s* ["']([^"'\s]+)["']                       # url = "..."
    | url \s+ ["']([^"'\s]+)["']                             # url "..."
    | maven \s* \( \s* ["']([^"'\s]+)["'] \s* \)            # maven("...")
    """,
    re.VERBOSE,
)


def _named_block_spans(text, names):
    """Return source ranges occupied by named Gradle blocks."""
    spans = []

    for name in names:
        pattern = re.compile(
            r"\b" + re.escape(name) + r"\s*\{"
        )
        for match in pattern.finditer(text):
            open_idx = text.find(
                "{",
                match.start(),
                match.end(),
            )
            if open_idx < 0:
                continue

            close_idx = _find_matching_brace(text, open_idx)
            if close_idx >= 0:
                spans.append((match.start(), close_idx + 1))

    return spans


def parse_gradle_repositories(
    build_text,
    include_plugin_repositories=False,
):
    """Extract repositories used for project dependencies.

    Repositories inside buildscript and pluginManagement blocks are
    excluded by default because those repositories resolve plugins and
    build-classpath dependencies, not normal application dependencies.
    """
    excluded_spans = (
        []
        if include_plugin_repositories
        else _named_block_spans(
            build_text,
            ("buildscript", "pluginManagement"),
        )
    )

    urls = []

    for match in _REPOSITORIES_BLOCK_RE.finditer(build_text):
        if any(
            block_start <= match.start() < block_end
            for block_start, block_end in excluded_spans
        ):
            continue

        open_idx = build_text.find(
            "{",
            match.start(),
            match.end(),
        )
        if open_idx < 0:
            continue

        close_idx = _find_matching_brace(build_text, open_idx)
        if close_idx < 0:
            continue
        block = build_text[open_idx : close_idx + 1]

        for url_match in _MAVEN_URL_RE.finditer(block):
            url = next(
                group
                for group in url_match.groups()
                if group
            ).rstrip("/")

            # An unresolved Gradle property/env interpolation, e.g.
            # url "${ARTIFACTORY_SOURCE}/repo-name" — we don't evaluate
            # Gradle expressions, and using the literal placeholder string
            # as an HTTP URL breaks every accessibility probe against it
            # silently. Confirmed live: find_accessible_version returned None
            # for an otherwise-accessible jackson-databind version because
            # the only "repo URL" on offer was the literal text
            # "${ARTIFACTORY_SOURCE}". Skip it so callers fall back to the
            # pipeline's own configured Artifactory base_url instead.
            if "$" in url:
                continue

            if url not in urls:
                urls.append(url)

    return urls


def has_unresolved_repo_url(build_text):
    """True when a repository declaration references a Gradle/env property
    we can't statically resolve, e.g. url "${ARTIFACTORY_SOURCE}/repo-name".

    Used to gate a real, but not free, fix: resolving the actual URL via a
    `--init-script` piggybacked on `gradle dependencies` (see
    parsers.gradle_tree.run_gradle_dependencies). That flag invalidates
    Gradle's configuration cache on every run — confirmed locally
    ("Configuration cache entry reused" without it, "entry stored" i.e.
    fully reconfigured with it) — which is enough overhead to tip a
    marginal tree resolution over its timeout on a large project. Only pay
    for it on repos that actually have something worth resolving.
    """
    for url_match in _MAVEN_URL_RE.finditer(build_text or ""):
        url = next((group for group in url_match.groups() if group), "")
        if "$" in url:
            return True
    return False


def normalize_gradle_version_for_probe(version):
    """Return a literal version suitable for an HTTP artifact probe.

    Exact Maven constraints such as ``[4.31.1]`` become ``4.31.1``.
    Ranges, dynamic versions, and variables return None because they
    must be resolved by Gradle rather than used as literal URL paths.
    """
    value = str(version or "").strip()
    if not value:
        return None

    # Avoid regex here. Exact constraints contain one value enclosed
    # by square brackets, while real ranges contain a comma.
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if inner and "," not in inner:
            value = inner
        else:
            return None

    if any(
        token in value
        for token in (
            ",",
            "[",
            "]",
            "(",
            ")",
            "$",
            "{",
            "}",
        )
    ):
        return None

    if value.endswith("+"):
        return None

    if value.lower() in {
        "latest",
        "release",
        "latest.release",
        "latest.integration",
    }:
        return None

    if not re.fullmatch(
        r"[0-9A-Za-z][0-9A-Za-z._+\-]*",
        value,
    ):
        return None

    return value


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

    for m in DEPENDENCY_PAREN_STRING_PATTERN.finditer(build_text):
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

    for m in _EACH_LIST_HEADER_RE.finditer(build_text):
        names = _QUOTED_ITEM_RE.findall(m.group("names"))
        if not names:
            continue
        each_close = _find_matching_brace(build_text, m.start("each_open"))
        if each_close < 0:
            continue
        original = build_text[m.start() : each_close + 1]
        version = _extract_strict_version(
            build_text[m.start("inner_open") : each_close]
        )
        if not version:
            continue
        config = m.group("config")
        group = m.group("group")
        for artifact in names:
            deps.append(
                GradleDep(
                    config=config,
                    group=group,
                    artifact=artifact,
                    version=version,
                    original=original,
                    match_start=m.start(),
                    match_end=each_close + 1,
                )
            )

    return sorted(deps, key=lambda d: d.match_start)


def collect_known_packages(
    deps: list[GradleDep],
    dep_tree_installed: dict | None = None,
) -> set[str]:
    """Return artifact names and group:artifact strings from declared/resolved Gradle dependencies."""
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


def parallel_fetch_versions(
    deps: list[GradleDep],
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
    workers: int,
    show_progress: bool,
) -> tuple[dict[str, list[MavenVersion]], list[dict]]:
    from shared.parallel import parallel_fetch

    # Deduplicate: Maven metadata lookup is keyed by group:artifact.
    unique_deps: dict[str, GradleDep] = {}
    for dep in deps:
        unique_deps.setdefault(f"{dep.group}:{dep.artifact}", dep)

    def fetch(dep: GradleDep) -> tuple[str, list[MavenVersion], str]:
        key = f"{dep.group}:{dep.artifact}"
        versions, error = get_available_versions(dep.group, dep.artifact, base_url, auth, timeout)
        return key, versions, error

    results, raw_errors = parallel_fetch(
        fetch,
        list(unique_deps.values()),
        f"Fetching Artifactory versions ({workers} workers)",
        workers,
    )
    error_rows = [{"dependency": k, "error": e} for k, e in raw_errors]
    return results, error_rows


_PRERELEASE_RE = re.compile(
    r"[-.](?:m\d+|rc\d*|alpha\d*|beta\d*|snapshot|milestone)",
    re.IGNORECASE,
)


_ACCESSIBILITY_CACHE = {}
MAX_VERSION_PROBES = 50


def _is_prerelease(v: MavenVersion) -> bool:
    return bool(_PRERELEASE_RE.search(v.raw))


def find_accessible_version(
    group: str,
    artifact: str,
    start: MavenVersion,
    available: list[MavenVersion],
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
    xray_host: str | None = None,
    repo_urls: list[str] | None = None,
    log_dir: str | None = None,
) -> str | None:
    """Return a non-vulnerable accessible same-major Maven version.

    Forward candidates are preferred in ascending order. If none are accessible,
    backward candidates are tried in descending order. Repository accessibility
    probes within each direction run concurrently while preserving that ordering.

    Thin Maven-specific adapter over `shared.version_search.find_safe_version`:
    builds the same-major forward/backward candidate lists and the multi-repo-URL
    accessibility probe, then delegates the CVE-filter + concurrent-probe
    orchestration to the shared implementation (also used by npm and PyPI).
    """
    from shared.version_search import find_safe_version

    # `timeout` here is gradle_timeout, sized for a real Gradle build (this
    # session raised it to 150-180s specifically so slow builds wouldn't be
    # mistaken for hangs). A version-accessibility probe is just an HTTP HEAD
    # and an Xray metadata POST -- reusing the build-scale timeout let a single
    # slow/hanging probe block for the full 150-180s, and with several related
    # packages needing their own probe (e.g. 8 io.netty:* artifacts flagged
    # together by one JFrog audit), that stacked into multi-minute stalls
    # confirmed live: a single package's proactive-check replacement search
    # measured ~90s while only 2 packages were probing concurrently against 8
    # available Artifactory slots -- concurrency headroom was never the
    # constraint, per-probe latency was. Cap it independently so a hung probe
    # fails fast instead of borrowing the build's patience.
    probe_timeout = min(timeout, 20)

    package = f"{group}:{artifact}"
    forward_candidates = sorted(
        v
        for v in available
        if v.major == start.major and v >= start and not _is_prerelease(v)
    )[:10]
    backward_candidates = sorted(
        (
            v
            for v in available
            if v.major == start.major and v < start and not _is_prerelease(v)
        ),
        reverse=True,
    )[:10]

    check_urls = list(
        dict.fromkeys((repo_urls or []) + ([base_url] if base_url else []))
    )
    def _accessible(version: MavenVersion) -> bool:
        return any(
            version_accessible(
                group,
                artifact,
                str(version),
                url,
                auth,
                probe_timeout,
            )
            for url in check_urls
        )

    search_start = time.perf_counter()

    result, _diagnostic = find_safe_version(
        forward_candidates,
        backward_candidates,
        _accessible,
        "maven",
        package,
        xray_host=xray_host,
        xray_auth=auth,
        timeout=probe_timeout,
    )

    from shared.build_validation import _dbg

    _dbg(
        log_dir,
        f"[perf] concurrent version search ({package}) completed in "
        f"{time.perf_counter() - search_start:.2f}s",
    )
    return str(result) if result is not None else None


