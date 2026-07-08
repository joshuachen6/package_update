"""NLP package-name extraction via the local claude CLI.

Identifies which known packages are mentioned in ADO task text.  All rows that
contain version numbers are sent to Claude in batched prompts so each subprocess
call covers many tasks at once.  Parallelism comes from concurrent chunk calls
via ThreadPoolExecutor, not one subprocess per task.

Entry point: batch_resolve(tasks, known_packages, ...) → (resolved_by_idx, errors).
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_MODEL = "haiku"
DEFAULT_EFFORT = "low"
DEFAULT_TIMEOUT = 120  # per-chunk call (covers many tasks)
DEFAULT_MAX_WORKERS = 4  # concurrent chunk calls
DEFAULT_BATCH_SIZE = 40  # tasks per chunk

_FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```", re.DOTALL)

# Matches the leading identifier of a task — handles scoped npm (@scope/pkg)
# and dotted/hyphenated Maven coords (org.springframework, spring-boot).
_FIRST_TOKEN_RE = re.compile(r"^(@[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|[A-Za-z0-9][A-Za-z0-9_.-]*)")


def _call_claude(
    prompt: str,
    model: str,
    effort: str,
    timeout: int,
    claude_cmd: str,
) -> tuple[str, str]:
    """
    Invoke the claude CLI in print mode and return (result_text, error).
    result_text is the model's raw output string; error is "" on success.
    """
    cmd = [
        claude_cmd,
        "-p",
        prompt,
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout}s"
    except Exception as exc:
        return "", f"subprocess error: {exc}"

    raw = proc.stdout or ""
    # Debug log lines (e.g. "[log_abc] post ...") are written to stdout before
    # the result JSON. Find the last line that starts a JSON object.
    json_line = next(
        (line for line in reversed(raw.splitlines()) if line.startswith("{")),
        None,
    )
    if not json_line:
        return "", f"no JSON in output: {(proc.stderr or raw)[:200]}"

    try:
        out = json.loads(json_line)
    except json.JSONDecodeError as exc:
        return "", f"JSON parse error: {exc}"

    # Auth failures return exit code 0 with is_error=true
    if out.get("is_error"):
        return "", f"claude error: {str(out.get('result', 'unknown'))[:300]}"

    return out.get("result", ""), ""


_PKG_NAME_RE = re.compile(r"^(@[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+|[A-Za-z0-9][A-Za-z0-9_.\-]*)$")


_FIXED_VERSION_LANGUAGE_RE = re.compile(
    r"\b("
    r"fixed\s+in|fix(?:es|ed)?\s+the\s+issue|"
    r"patched\s+in|problem\s+is\s+patched\s+in|"
    r"upgrade\s+to|upgraded\s+to|users\s+should\s+upgrade\s+to|"
    r"resolved\s+in|remediated\s+in"
    r")\b",
    re.IGNORECASE,
)


def _constraint_from_task_language(text: str) -> str | None:
    """
    Return a deterministic constraint when the task text uses clear remediation
    language. es describe the mentioned version as acceptable, so the
    correct constraint is >= even if the NLP model classifies it as >.
    """
    return ">=" if _FIXED_VERSION_LANGUAGE_RE.search(text or "") else None


def _is_plausible_package_name(name: str) -> bool:
    """
    Lightweight guard against hallucinated names.
    Accepts npm-style names (optionally scoped) and simple Maven artifact IDs.
    Rejects anything with spaces, control characters, or implausible length.
    """
    return isinstance(name, str) and 1 < len(name) < 150 and bool(_PKG_NAME_RE.match(name))


def _parse_batch_response(
    raw: str,
    known_packages: set[str],
    allow_unlisted: bool = False,
) -> dict[int, dict[str, str]]:
    """
    Parse Claude's batch response into {chunk_local_index: {pkg: constraint}}.

    Expected format:
      {"0": {"pkg-a": ">="}, "1": {}, "2": {"pkg-b": ">=", "pkg-c": ">"}}

    constraint values:
      ">="  the mentioned version is the minimum acceptable (include it)
      ">"   the mentioned version is itself bad; need strictly above it

    When allow_unlisted=False (default), only known_packages names are kept.
    When allow_unlisted=True, also accepts plausible-looking unlisted names.
    """
    cleaned = _FENCE_RE.sub("", raw).strip()
    obj = None
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(m.group(0))

    if not isinstance(obj, dict):
        return {}

    result: dict[int, dict[str, str]] = {}
    for k, v in obj.items():
        try:
            idx = int(k)
        except (ValueError, TypeError):
            continue
        if not isinstance(v, dict):
            continue
        entry: dict[str, str] = {}
        for pkg, constraint in v.items():
            if not isinstance(pkg, str):
                continue
            if pkg not in known_packages and (
                not allow_unlisted or not _is_plausible_package_name(pkg)
            ):
                continue
            entry[pkg] = ">" if constraint == ">" else ">="
        result[idx] = entry
    return result


def _resolve_chunk(
    chunk: list[tuple[int, int | None, str]],  # (list_idx, task_id, text)
    known_packages: set[str],
    model: str,
    effort: str,
    timeout: int,
    claude_cmd: str,
    allow_unlisted: bool = True,
) -> tuple[dict[int, dict[str, str]], str]:
    """
    Send one batch of tasks to Claude in a single subprocess call.
    Returns ({list_idx: {pkg: constraint}}, error_message).
    constraint is ">=" (version is minimum acceptable) or ">" (version itself is bad; need strictly above).
    """
    pkg_list = "\n".join(f"- {p}" for p in sorted(known_packages))

    task_parts: list[str] = []
    for i, (_, _, text) in enumerate(chunk):
        header = f"Task {i}:"
        task_parts.append(f"{header}\n{text.strip()}")
    tasks_block = "\n\n".join(task_parts)

    if allow_unlisted:
        unlisted_instruction = (
            "Also include package names that are explicitly mentioned in the task text "
            "but do NOT appear in the known list — they may need to be added as "
            "transitive dependency version overrides. "
            "Do NOT invent names; only include names that literally appear in the task text."
        )
    else:
        unlisted_instruction = "Use only names from the known list."

    prompt = (
        "You are analyzing software dependency update tasks.\n\n"
        f"Known packages:\n{pkg_list}\n\n"
        "For each numbered task below, identify which packages are mentioned or discussed.\n"
        "Return a JSON object where keys are task numbers (as strings) and values are objects "
        "mapping package name to a version constraint:\n"
        '  ">=" means the mentioned version is the minimum acceptable (upgrade to at least this version)\n'
        '  ">"  means the mentioned version is itself bad (e.g. vulnerable, breaking); need strictly above it\n'
        f"{unlisted_instruction}\n"
        'Example: {"0": {"pkg-a": ">=", "minimatch": ">="}, "1": {}, "2": {"pkg-b": ">", "pkg-c": ">="}}\n'
        "Reply with the JSON object only.\n\n"
        f"{tasks_block}"
    )

    result_text, err = _call_claude(prompt, model, effort, timeout, claude_cmd)
    if err:
        return {}, err

    local_map = _parse_batch_response(result_text, known_packages, allow_unlisted)

    # Map chunk-local indices back to global list indices
    return {chunk[i][0]: local_map.get(i, {}) for i in range(len(chunk))}, ""


def _deterministic_package_hints(text: str, known_packages: set[str]) -> dict[str, str]:
    """Infer package names from highly specific syntax that Claude may miss."""
    hints: dict[str, str] = {}
    if "lodash" in known_packages and re.search(r"(?<![A-Za-z0-9])_\.", text or ""):
        hints["lodash"] = _constraint_from_task_language(text) or ">="
    return hints


def batch_resolve(
    tasks: list[tuple[int | None, str]],
    known_packages: set[str],
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    timeout: int = DEFAULT_TIMEOUT,
    workers: int = DEFAULT_MAX_WORKERS,
    claude_cmd: str = "claude",
    batch_size: int = DEFAULT_BATCH_SIZE,
    allow_unlisted: bool = True,
) -> tuple[dict[int, dict[str, str]], list[dict]]:
    """
    Resolve all tasks by sending them to Claude in batched prompts.

    Parameters
    ----------
    tasks     : List of (task_id, text).
    batch_size: Tasks per Claude call. Each call is one subprocess.
    workers   : Concurrent subprocess calls.

    Returns
    -------
    resolved_by_idx : {list_index: {pkg: constraint}}
                      constraint is ">=" or ">"
    errors          : [{"chunk_start": int, "chunk_size": int, "error": str}]
    """
    if not tasks:
        return {}, []

    indexed = [(i, tid, txt) for i, (tid, txt) in enumerate(tasks)]
    chunks = [indexed[i : i + batch_size] for i in range(0, len(indexed), batch_size)]

    resolved: dict[int, dict[str, str]] = {}
    errors: list[dict] = []

    from shared.utils import ProgressBar

    progress = ProgressBar(len(chunks), "NLP extraction (Claude)")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_chunk = {
            executor.submit(
                _resolve_chunk,
                chunk,
                known_packages,
                model,
                effort,
                timeout,
                claude_cmd,
                allow_unlisted,
            ): chunk
            for chunk in chunks
        }
        for future in as_completed(future_to_chunk):
            chunk = future_to_chunk[future]
            chunk_result, err = future.result()
            for list_idx, pkg_map in chunk_result.items():
                task_text = indexed[list_idx][2]
                deterministic_hints = _deterministic_package_hints(task_text, known_packages)
                if pkg_map:
                    deterministic_constraint = _constraint_from_task_language(task_text)
                    if deterministic_constraint == ">=":
                        pkg_map = {
                            pkg: ">=" if constraint == ">" else constraint
                            for pkg, constraint in pkg_map.items()
                        }
                if deterministic_hints:
                    pkg_map = {
                        **pkg_map,
                        **{
                            pkg: constraint
                            for pkg, constraint in deterministic_hints.items()
                            if pkg not in pkg_map
                        },
                    }
                resolved[list_idx] = pkg_map
            progress.update()
            if err:
                errors.append(
                    {
                        "chunk_start": chunk[0][0],
                        "chunk_size": len(chunk),
                        "error": err,
                    }
                )
                from loguru import logger

                logger.warning(
                    f"Claude resolver chunk (tasks {chunk[0][0]}-{chunk[-1][0]}, "
                    f"size={len(chunk)}) failed: {err}"
                )

    return resolved, errors
