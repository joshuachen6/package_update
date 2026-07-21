from __future__ import annotations

from pathlib import Path


def write_python_dependency_file(updated_text, input_path, output_path=None, *, in_place=False):
    target = Path(input_path if in_place else (output_path or input_path))
    bak = target.with_suffix(target.suffix + ".bak")
    if not bak.exists() and target.exists():
        bak.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.write_text(updated_text, encoding="utf-8")
    return str(target)
