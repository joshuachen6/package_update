from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

OPS = ("==", "~=", ">=", "<=", ">", "<")
_TOML_DEP_RE = re.compile(
    r"""^\s*['"]?(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[^\]]+\])?(?P<op>==|~=|>=|<=|>|<)(?P<version>[^;#,\]"'\s]+).*$"""
)


@dataclass(frozen=True)
class PythonRequirement:
    name: str
    version: str
    operator: str
    line_index: int
    raw_line: str
    normalized_name: str
    source: str = "requirements"
    constraint: str = ""


def normalize_python_package(name):
    return name.replace("_", "-").lower()


def _split_commentless(line):
    return line.split("#", 1)[0].strip()


def _extract_requirement_constraint(line):
    body = _split_commentless(line).split(";", 1)[0].strip()
    match = re.match(
        r"^\s*[A-Za-z0-9_.-]+(?:\[[^\]]+\])?\s*(?P<constraint>.+?)\s*$",
        body,
    )
    if not match:
        return ""
    constraint = match.group("constraint").strip().strip('"').strip("'")
    if not any(constraint.startswith(op) for op in OPS):
        return ""
    return constraint


def _parse_requirement_line(line):
    body = _split_commentless(line).split(";", 1)[0].strip()
    match = re.match(
        r"^\s*(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?"
        r"\s*(?P<op>==|~=|>=|<=|>|<)\s*"
        r"(?P<version>[^,\s\"']+)",
        body,
    )
    if not match:
        return None
    return (
        match.group("name"),
        match.group("op"),
        match.group("version"),
    )


def _version_tuple(value):
    match = re.match(r"^\s*[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(value))
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _compatible_upper_bound(version):
    parts = [int(part) for part in re.findall(r"\d+", version)]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0] + 1, 0, 0
    return parts[0], parts[1] + 1, 0


def version_satisfies_constraint(version, constraint):
    """Evaluate the supported requirements.txt comparison subset.

    Supports comma-separated intersections using ==, ~=, >=, <=, >, and <.
    Exact pins are intentionally not used as search bounds because remediation
    must remain able to replace a vulnerable exact pin.
    """
    if not constraint:
        return True

    clauses = [clause.strip() for clause in constraint.split(",") if clause.strip()]
    if not clauses or all(clause.startswith("==") for clause in clauses):
        return True

    candidate = _version_tuple(version)
    if candidate is None:
        return False

    for clause in clauses:
        match = re.match(r"^(==|~=|>=|<=|>|<)\s*(.+?)\s*$", clause)
        if not match:
            return False

        operator, raw_bound = match.groups()
        bound = _version_tuple(raw_bound)
        if bound is None:
            return False

        if operator == "==" and candidate != bound:
            return False
        if operator == ">=" and candidate < bound:
            return False
        if operator == ">" and candidate <= bound:
            return False
        if operator == "<=" and candidate > bound:
            return False
        if operator == "<" and candidate >= bound:
            return False
        if operator == "~=":
            upper = _compatible_upper_bound(raw_bound)
            if upper is None or candidate < bound or candidate >= upper:
                return False

    return True


def parse_requirements_text(text):
    requirements = []
    for idx, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(("-", "--")):
            continue
        parsed = _parse_requirement_line(line)
        if not parsed:
            continue
        name, op, version = parsed
        requirements.append(
            PythonRequirement(
                name=name,
                version=version,
                operator=op,
                line_index=idx,
                raw_line=line,
                normalized_name=normalize_python_package(name),
                source="requirements",
                constraint=_extract_requirement_constraint(line),
            )
        )
    return requirements


def parse_requirements_file(path):
    text = Path(path).read_text(encoding="utf-8")
    return text, parse_requirements_text(text)
def _toml_table_name(line):
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped.strip("[]").strip()
    return None


def _is_supported_pyproject_dependency_table(table):
    if table in {
        "project",
        "tool.poetry.dependencies",
        "tool.poetry.group.dev.dependencies",
        "tool.poetry.dev-dependencies",
    }:
        return True
    return bool(table and table.startswith("tool.poetry.group.") and table.endswith(".dependencies"))


def _parse_project_dependency_string(line):
    stripped = line.strip().rstrip(",").strip('"').strip("'")
    match = _TOML_DEP_RE.match(stripped)
    if not match:
        return None
    return match.group("name"), match.group("op"), match.group("version")


def _extract_poetry_version_spec(value):
    value = value.strip().rstrip(",")
    if value.startswith("{"):
        match = re.search(r"""version\s*=\s*(['"])(?P<spec>[^'"]+)\1""", value)
        return match.group("spec") if match else None
    return value.strip().strip('"').strip("'")


def _parse_poetry_dependency_kv(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    name = key.strip().strip('"').strip("'")
    if not name or name.lower() == "python":
        return None
    spec = _extract_poetry_version_spec(value)
    if not spec:
        return None
    for op in OPS:
        if spec.startswith(op):
            version = spec[len(op):].strip()
            if version:
                return name, op, version
    return None


def parse_pyproject_text(text):
    requirements = []
    table = None
    in_project_dependencies = False

    for idx, line in enumerate(text.splitlines()):
        maybe_table = _toml_table_name(line)
        if maybe_table is not None:
            table = maybe_table
            in_project_dependencies = False
            continue

        stripped = line.strip()
        if table == "project" and stripped.startswith("dependencies") and "=" in stripped and "[" in stripped:
            in_project_dependencies = True
            continue

        if in_project_dependencies:
            if stripped.startswith("]"):
                in_project_dependencies = False
                continue
            parsed = _parse_project_dependency_string(line)
            if parsed:
                name, op, version = parsed
                requirements.append(
                    PythonRequirement(
                        name=name,
                        version=version,
                        operator=op,
                        line_index=idx,
                        raw_line=line,
                        normalized_name=normalize_python_package(name),
                        source="pyproject",
                        constraint=_extract_requirement_constraint(line),
                    )
                )
            continue

        if table and table != "project" and _is_supported_pyproject_dependency_table(table):
            parsed = _parse_poetry_dependency_kv(line)
            if parsed:
                name, op, version = parsed
                requirements.append(
                    PythonRequirement(
                        name=name,
                        version=version,
                        operator=op,
                        line_index=idx,
                        raw_line=line,
                        normalized_name=normalize_python_package(name),
                        source="pyproject",
                        constraint=_extract_requirement_constraint(line),
                    )
                )

    return requirements


def parse_pyproject_file(path):
    text = Path(path).read_text(encoding="utf-8")
    return text, parse_pyproject_text(text)
def parse_python_dependency_file(path):
    p = Path(path)
    if p.name == "pyproject.toml":
        return parse_pyproject_file(p)
    return parse_requirements_file(p)


def update_requirement_line(line, new_version):
    parsed = _parse_requirement_line(line)
    if not parsed:
        return line
    _, op, old_version = parsed
    return line.replace(op + old_version, op + new_version, 1)


def update_pyproject_line(line, new_version):
    parsed = _parse_project_dependency_string(line)
    if parsed:
        _, op, old_version = parsed
        return line.replace(op + old_version, op + new_version, 1)
    parsed = _parse_poetry_dependency_kv(line)
    if parsed:
        _, op, old_version = parsed
        return line.replace(op + old_version, op + new_version, 1)
    return line


def update_python_dependency_text(text, changes, file_type="requirements"):
    lines = text.splitlines()
    trailing_newline = text.endswith(chr(10))
    for change in changes:
        idx = change.get("line_index")
        if not isinstance(idx, int) or idx not in range(len(lines)):
            continue
        if file_type == "pyproject":
            lines[idx] = update_pyproject_line(lines[idx], change["new_version"])
        else:
            lines[idx] = update_requirement_line(lines[idx], change["new_version"])
    updated = chr(10).join(lines)
    if trailing_newline:
        updated += chr(10)
    return updated


def update_requirements_text(text, changes):
    return update_python_dependency_text(text, changes, file_type="requirements")


def dependency_file_type(path):
    return "pyproject" if Path(path).name == "pyproject.toml" else "requirements"


def is_supported_python_dependency_file(path):
    p = Path(path)
    name = p.name.lower()
    if name == "pyproject.toml":
        return True
    if name in {"requirements.txt", "requirements-dev.txt", "requirements-test.txt", "constraints.txt"}:
        return True
    return p.parent.name == "requirements" and p.suffix == ".txt"
