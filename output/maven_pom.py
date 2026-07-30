"""Write updated Maven pom.xml files."""
from __future__ import annotations

import re
from pathlib import Path


_DM_SECTION_RE = re.compile(
    r'(<dependencyManagement>[\s\S]*?<dependencies>)([\s\S]*?)(</dependencies>[\s\S]*?</dependencyManagement>)',
    re.DOTALL,
)
_DEPS_SECTION_RE = re.compile(r'</dependencies>', re.DOTALL)


def _apply_span_replacements(
    pom_text: str,
    replacements: list[tuple[tuple[int, int], str]],
) -> str:
    """Apply (span, new_value) replacements from end to start to preserve offsets."""
    sorted_replacements = sorted(replacements, key=lambda r: r[0][0], reverse=True)
    result = pom_text
    for (start, end), new_val in sorted_replacements:
        result = result[:start] + new_val + result[end:]
    return result


def _build_dm_dep_block(group: str, artifact: str, version: str, indent: str = '            ') -> str:
    """Build a <dependency> block for insertion into <dependencyManagement>."""
    i = indent
    return (
        f'{i}<dependency>\n'
        f'{i}    <groupId>{group}</groupId>\n'
        f'{i}    <artifactId>{artifact}</artifactId>\n'
        f'{i}    <version>{version}</version>\n'
        f'{i}</dependency>'
    )


def apply_pom_changes(
    pom_text: str,
    changes: list[dict],
    dm_overrides: list[dict],
) -> str:
    """Apply version changes and dependency management overrides to pom_text.

    changes: list of dicts with keys:
        dependency, old_version, new_version, version_span, property_span
        (version_span or property_span must be non-None)
    dm_overrides: list of dicts with keys:
        dependency, old_version, new_version
        (adds/updates <dependencyManagement> entries for transitives)
    """
    replacements: list[tuple[tuple[int, int], str]] = []

    for ch in changes:
        # Prefer property span (updating a shared property updates all users at once)
        span = ch.get('property_span') or ch.get('version_span')
        if span:
            replacements.append((span, ch['new_version']))

    pom_text = _apply_span_replacements(pom_text, replacements)

    # Add/update dependencyManagement entries for transitives
    if dm_overrides:
        dm_m = _DM_SECTION_RE.search(pom_text)
        new_blocks = []
        for ov in dm_overrides:
            group, artifact = ov['dependency'].split(':', 1)
            new_version = ov['new_version']
            # Check if the dep is already in the DM section
            ga_pattern = re.compile(
                rf'<groupId>\s*{re.escape(group)}\s*</groupId>[\s\S]*?'
                rf'<artifactId>\s*{re.escape(artifact)}\s*</artifactId>',
                re.DOTALL,
            )
            if dm_m and ga_pattern.search(dm_m.group(2)):
                # Already present - update its version span in the current pom_text
                # Re-search after previous replacements
                dm_m2 = _DM_SECTION_RE.search(pom_text)
                if dm_m2:
                    dm_inner = dm_m2.group(2)
                    dm_inner_start = dm_m2.start(2)
                    # Find the dep block for this GA
                    dep_block_re = re.compile(
                        r'<dependency>[\s\S]*?</dependency>', re.DOTALL
                    )
                    for dep_m in dep_block_re.finditer(dm_inner):
                        block = dep_m.group()
                        g = re.search(r'<groupId>\s*([^\s<]+)\s*</groupId>', block)
                        a = re.search(r'<artifactId>\s*([^\s<]+)\s*</artifactId>', block)
                        if g and a and g.group(1) == group and a.group(1) == artifact:
                            vm = re.search(r'<version>([\s\S]*?)</version>', block, re.DOTALL)
                            if vm:
                                raw = vm.group(1)
                                stripped = raw.strip()
                                off = raw.index(stripped) if stripped else 0
                                abs_start = dm_inner_start + dep_m.start() + vm.start(1) + off
                                abs_end = abs_start + len(stripped)
                                pom_text = pom_text[:abs_start] + new_version + pom_text[abs_end:]
                                # Re-compute dm_m after modification
                                dm_m = _DM_SECTION_RE.search(pom_text)
                            break
            else:
                new_blocks.append(_build_dm_dep_block(group, artifact, new_version))

        if new_blocks:
            # Insert new blocks into existing <dependencyManagement> or create it
            dm_m = _DM_SECTION_RE.search(pom_text)
            insertion = '\n'.join(new_blocks) + '\n'
            if dm_m:
                # Insert before closing </dependencies> of <dependencyManagement>
                close_tag_pos = pom_text.index('</dependencies>', dm_m.start())
                pom_text = pom_text[:close_tag_pos] + insertion + pom_text[close_tag_pos:]
            else:
                # Insert a new <dependencyManagement> section before the first <dependencies>
                first_deps = re.search(r'<dependencies>', pom_text)
                if first_deps:
                    indent = '    '
                    dm_section = (
                        f'{indent}<dependencyManagement>\n'
                        f'{indent}    <dependencies>\n'
                        + '\n'.join(
                            _build_dm_dep_block(
                                ov['dependency'].split(':', 1)[0],
                                ov['dependency'].split(':', 1)[1],
                                ov['new_version'],
                                f'{indent}        ',
                            )
                            for ov in dm_overrides
                        )
                        + f'\n{indent}    </dependencies>\n'
                        f'{indent}</dependencyManagement>\n'
                    )
                    pom_text = pom_text[:first_deps.start()] + dm_section + pom_text[first_deps.start():]

    return pom_text


def write_pom_file(
    updated_text: str,
    input_path: str,
    output_path: str | None = None,
    *,
    in_place: bool = False,
) -> str:
    target = Path(input_path if in_place else (output_path or input_path))
    bak = target.with_suffix(target.suffix + '.bak')
    if not bak.exists() and target.exists():
        bak.write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
    target.write_text(updated_text, encoding='utf-8')
    return str(target)
