"""Parse Maven pom.xml files and resolve dependency trees via mvn dependency:tree."""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from shared.maven_version import MavenVersion


_PROP_REF_RE = re.compile(r'^\$\{([^}]+)\}$')

# Dep block patterns (no namespace prefix — standard pom.xml convention)
_DEP_BLOCK_RE = re.compile(r'<dependency>([\s\S]*?)</dependency>', re.DOTALL)
_DM_RE = re.compile(r'<dependencyManagement>([\s\S]*?)</dependencyManagement>', re.DOTALL)
_DEPS_SECTION_RE = re.compile(r'<dependencies>([\s\S]*?)</dependencies>', re.DOTALL)
_PROPERTIES_BLOCK_RE = re.compile(r'<properties>([\s\S]*?)</properties>', re.DOTALL)
_PROP_CHILD_RE = re.compile(r'<(\w[\w.-]*)>([\s\S]*?)</\1>', re.DOTALL)

# Maven dependency:tree line — group:artifact:type:version[:scope]
_MAVEN_TREE_LINE_RE = re.compile(
    r'([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):[A-Za-z0-9_.-]+:([A-Za-z0-9_.+\-]+)(?::[A-Za-z0-9_.-]+)?'
)


@dataclass
class PomDep:
    group: str
    artifact: str
    version: str            # resolved (property substituted)
    version_raw: str        # as written in pom (may be ${prop})
    scope: str
    is_managed: bool        # True = from <dependencyManagement>
    property_key: str | None
    version_span: tuple[int, int] | None   # span of version value in pom_text
    property_span: tuple[int, int] | None  # span of property value in pom_text


@dataclass
class PomParsed:
    file_path: str
    pom_text: str
    deps: list[PomDep]
    properties: dict[str, str]
    property_spans: dict[str, tuple[int, int]]


def _elem_text(block_text: str, tag: str) -> str:
    """Extract trimmed text of the first <tag> element in block_text."""
    m = re.search(rf'<{re.escape(tag)}\b[^>]*>(.*?)</{re.escape(tag)}>', block_text, re.DOTALL)
    return (m.group(1).strip() if m else '')


def _version_span_in_block(pom_text: str, block_start: int, block_text: str) -> tuple[int, int] | None:
    """Return the char span of the trimmed version value in pom_text."""
    vm = re.search(r'<version\b[^>]*>([\s\S]*?)</version>', block_text, re.DOTALL)
    if not vm:
        return None
    raw = vm.group(1)
    stripped = raw.strip()
    if not stripped:
        return None
    off = raw.index(stripped)
    abs_start = block_start + vm.start(1) + off
    return (abs_start, abs_start + len(stripped))


def _parse_blocks_in_section(
    pom_text: str,
    section_offset: int,
    section_text: str,
    is_managed: bool,
    properties: dict[str, str],
    property_spans: dict[str, tuple[int, int]],
) -> list[PomDep]:
    """Extract PomDep list from the text of a <dependencies> section."""
    deps: list[PomDep] = []
    for m in _DEP_BLOCK_RE.finditer(section_text):
        block_text = m.group()
        block_start = section_offset + m.start()

        group = _elem_text(block_text, 'groupId')
        artifact = _elem_text(block_text, 'artifactId')
        if not group or not artifact:
            continue

        version_raw = _elem_text(block_text, 'version')
        scope = _elem_text(block_text, 'scope') or 'compile'

        prop_m = _PROP_REF_RE.match(version_raw)
        property_key = prop_m.group(1) if prop_m else None
        resolved = properties.get(property_key, version_raw) if property_key else version_raw

        vs = _version_span_in_block(pom_text, block_start, block_text) if version_raw else None
        ps = property_spans.get(property_key) if property_key else None

        deps.append(PomDep(
            group=group,
            artifact=artifact,
            version=resolved,
            version_raw=version_raw,
            scope=scope,
            is_managed=is_managed,
            property_key=property_key,
            version_span=vs,
            property_span=ps,
        ))
    return deps


def parse_pom_file(file_path: str) -> PomParsed:
    pom_text = Path(file_path).read_text(encoding='utf-8')
    return parse_pom_text(pom_text, file_path)


def parse_pom_text(pom_text: str, file_path: str = '') -> PomParsed:
    """Parse a pom.xml text and return a PomParsed with all dep declarations."""
    # 1. Extract properties and their text spans
    properties: dict[str, str] = {}
    property_spans: dict[str, tuple[int, int]] = {}

    pm = _PROPERTIES_BLOCK_RE.search(pom_text)
    if pm:
        props_text = pm.group(1)
        props_offset = pm.start(1)
        for child_m in _PROP_CHILD_RE.finditer(props_text):
            key = child_m.group(1)
            raw_val = child_m.group(2)
            stripped = raw_val.strip()
            if key and stripped:
                properties[key] = stripped
                off = raw_val.index(stripped)
                abs_start = props_offset + child_m.start(2) + off
                property_spans[key] = (abs_start, abs_start + len(stripped))

    # 2. Managed deps from <dependencyManagement>
    all_deps: list[PomDep] = []
    dm_m = _DM_RE.search(pom_text)
    dm_range = (0, 0)
    if dm_m:
        dm_range = (dm_m.start(), dm_m.end())
        all_deps.extend(_parse_blocks_in_section(
            pom_text,
            dm_m.start(1),
            dm_m.group(1),
            True,
            properties,
            property_spans,
        ))

    # 3. Direct deps — every <dependencies> section NOT inside <dependencyManagement>
    for deps_m in _DEPS_SECTION_RE.finditer(pom_text):
        if dm_range[0] <= deps_m.start() < dm_range[1]:
            continue  # skip the DM inner <dependencies>
        all_deps.extend(_parse_blocks_in_section(
            pom_text,
            deps_m.start(1),
            deps_m.group(1),
            False,
            properties,
            property_spans,
        ))

    print(f"Found {len(all_deps)} dependency declarations in {file_path or 'pom.xml'}")
    return PomParsed(
        file_path=file_path,
        pom_text=pom_text,
        deps=all_deps,
        properties=properties,
        property_spans=property_spans,
    )


def _extract_repo_ids(pom_text: str) -> list[str]:
    """Return all <repository><id> values declared in the pom.xml.

    These are used to create matching <server> entries in the generated
    settings.xml so Maven can authenticate against each repo directly,
    not just through the mirror.  Parent POM imports (which live in the
    local .m2 cache and reference their own repo IDs) are intentionally
    not parsed here — the mirror + broad server coverage handles those.
    """
    ids: list[str] = []
    # Match inside <repositories> and <pluginRepositories> sections
    _REPO_SECTIONS_RE = re.compile(
        r'<(?:plugin)?[Rr]epositories>([\s\S]*?)</(?:plugin)?[Rr]epositories>',
        re.DOTALL,
    )
    _REPO_ID_RE = re.compile(r'<id\b[^>]*>\s*([^\s<]+)\s*</id>')
    for section_m in _REPO_SECTIONS_RE.finditer(pom_text):
        for id_m in _REPO_ID_RE.finditer(section_m.group(1)):
            repo_id = id_m.group(1).strip()
            if repo_id and repo_id not in ids:
                ids.append(repo_id)
    return ids


def _write_temp_settings(
    base_url: str,
    auth: tuple[str, str],
    extra_server_ids: list[str] | None = None,
) -> str:
    """Write a temporary Maven settings.xml that routes all repositories through
    Artifactory with the provided credentials.

    Two complementary mechanisms are used so that credentials reach Maven
    regardless of whether the request goes through the mirror or directly to
    a repository by its original ID (which happens for parent POMs already
    cached in ~/.m2 that embed their own <repositories> blocks):

      1. mirrorOf=* mirror — redirects every remote repo to base_url and
         authenticates via the 'artifactory-proxy' server entry.
      2. Per-ID server entries — one entry for each repo ID found in the
         pom.xml (e.g. 'confluent', 'spring-milestones') so Maven can
         authenticate against those repos even if the mirror lookup doesn't
         intercept the request.

    Returns the file path. Caller must delete it when done.
    """
    username, password = auth

    def _esc(s: str) -> str:
        return (
            s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;')
        )

    u, p = _esc(username), _esc(password)

    # Build per-repo server entries (mirror entry is always first)
    all_ids = ['artifactory-proxy'] + [i for i in (extra_server_ids or []) if i != 'artifactory-proxy']
    server_blocks = '\n'.join(
        f'    <server>\n'
        f'      <id>{sid}</id>\n'
        f'      <username>{u}</username>\n'
        f'      <password>{p}</password>\n'
        f'    </server>'
        for sid in all_ids
    )

    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"\n'
        '          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0'
        ' http://maven.apache.org/xsd/settings-1.0.0.xsd">\n'
        '  <mirrors>\n'
        '    <mirror>\n'
        '      <id>artifactory-proxy</id>\n'
        '      <mirrorOf>*</mirrorOf>\n'
        f'      <url>{base_url}</url>\n'
        '    </mirror>\n'
        '  </mirrors>\n'
        '  <servers>\n'
        f'{server_blocks}\n'
        '  </servers>\n'
        '</settings>\n'
    )

    fd, path = tempfile.mkstemp(suffix='.xml', prefix='pkg_update_mvn_settings_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(content)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise
    return path


def get_maven_cmd(project_dir: str) -> str:
    """Return mvnw path if present, else 'mvn'."""
    project_path = Path(project_dir)
    for wrapper in ('mvnw', 'mvnw.cmd', 'mvnw.bat'):
        candidate = project_path / wrapper
        if candidate.is_file():
            return str(candidate.resolve())
    return 'mvn'


def _run_cmd(
    cmd: list[str],
    project_dir: str,
    timeout: int,
) -> tuple[str | None, str | None, str]:
    """Run a command; return (tree_output_or_None, short_error_or_None, full_combined_output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        msg = f'timed out after {timeout}s'
        return None, msg, msg
    except FileNotFoundError:
        msg = f'command not found: {cmd[0]!r}'
        return None, msg, msg
    except Exception as exc:
        return None, str(exc), str(exc)

    stdout = result.stdout or ''
    stderr = (result.stderr or '').strip()
    full_output = f'--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}' if stderr else stdout

    has_tree = ('+- ' in stdout or '\\- ' in stdout)
    tree_out = stdout if has_tree else None

    if result.returncode != 0:
        msg = f'exit code {result.returncode}'
        if stderr:
            msg = f'{msg}\n{stderr[:500]}'
        return tree_out, msg, full_output
    return tree_out, None, full_output


def run_maven_dependency_tree(
    project_dir: str,
    pom_file: str,
    maven_cmd: str,
    timeout: int,
    base_url: str | None = None,
    auth: tuple[str, str] | None = None,
    extra_server_ids: list[str] | None = None,
) -> tuple[str | None, str | None, str]:
    """Run mvn dependency:tree with fallback variants.

    Returns (tree_output_or_None, short_error_or_None, verbose_log_for_error_file).

    When base_url and auth are provided a temporary settings.xml is generated
    that routes all Maven repository traffic through Artifactory with the given
    credentials (same as how the Gradle and HTTP registry calls work).

    Tries progressively simpler invocations so that older Maven wrappers
    (pre-3.6.1) still work and projects with partial resolution failures still
    produce a usable dependency tree.
    """
    settings_path: str | None = None
    try:
        if base_url and auth:
            settings_path = _write_temp_settings(base_url, auth, extra_server_ids)

        sf = ['-s', settings_path] if settings_path else []

        # Note: --no-transfer-progress requires Maven >= 3.6.1 — omitted to stay
        # compatible with older mvnw wrappers common in enterprise repos.
        candidates = [
            [maven_cmd, 'dependency:tree', '-f', pom_file, '-B'] + sf,
            # Without -f: let Maven discover pom.xml from project_dir
            [maven_cmd, 'dependency:tree', '-B'] + sf,
            # No -B: handles edge cases where batch mode misbehaves
            [maven_cmd, 'dependency:tree', '-f', pom_file] + sf,
        ]

        last_err: str | None = None
        last_full: str = ''

        for cmd in candidates:
            tree_out, err, full_output = _run_cmd(cmd, project_dir, timeout)
            if tree_out:
                # Partial tree is usable — dependency resolution warnings are
                # common in enterprise repos with restricted artifact scopes.
                return tree_out, err, full_output
            if err and 'command not found' in err:
                return None, err, full_output  # binary missing — retrying won't help
            last_err = err or last_err
            last_full = full_output or last_full

        # All silent attempts failed. Re-run with -e so the error log contains
        # stack traces, plugin errors, and resolution detail — not just exit code 1.
        verbose_cmd = [maven_cmd, 'dependency:tree', '-f', pom_file, '-e'] + sf
        _, _, verbose_full = _run_cmd(verbose_cmd, project_dir, timeout)

        creds_note = f'Artifactory mirror: {base_url}' if base_url else 'no Artifactory mirror configured'
        header = (
            f'cmd: {" ".join(candidates[0])}\n'
            f'cwd: {project_dir}\n'
            f'error: {last_err}\n'
            f'{creds_note}\n\n'
            '--- verbose run (-e) ---\n'
        )
        return None, last_err, header + (verbose_full or last_full)

    finally:
        if settings_path:
            with contextlib.suppress(OSError):
                os.unlink(settings_path)


def parse_maven_dep_tree(output: str) -> tuple[dict[str, MavenVersion], dict[str, set[str]]]:
    """Parse `mvn dependency:tree` stdout.

    Returns:
        installed  — {group:artifact: resolved_MavenVersion}
        parents_of — {transitive_g:a: {direct_parent_g:a, ...}}
    """
    installed: dict[str, MavenVersion] = {}
    parents_of: dict[str, set[str]] = {}
    stack: list[tuple[int, str]] = []  # (depth, key)

    for raw_line in output.splitlines():
        # Strip [INFO] prefix
        content = raw_line.strip()
        if content.startswith('[INFO]'):
            content = content[6:].lstrip()

        if '+- ' not in content and '\\- ' not in content:
            continue

        # Depth = number of leading '|  ' (3-char) indent units
        depth = 0
        pos = 0
        while pos + 3 <= len(content) and content[pos:pos + 3] == '|  ':
            depth += 1
            pos += 3

        m = _MAVEN_TREE_LINE_RE.search(content, pos)
        if not m:
            continue

        group, artifact, version_str = m.group(1), m.group(2), m.group(3)
        # Skip 'omitted' or duplicate markers
        if '(omitted' in content[m.end():m.end() + 20]:
            continue

        version = MavenVersion.parse(version_str)
        if not version:
            continue

        key = f'{group}:{artifact}'
        installed[key] = version

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            parents_of.setdefault(key, set()).add(stack[-1][1])

        stack.append((depth, key))

    return installed, parents_of
