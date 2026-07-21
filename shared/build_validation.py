from __future__ import annotations

import contextlib
import csv
import json
import os
import re
import signal
import subprocess
import time
from datetime import datetime
from collections.abc import Callable
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from typing import Any

from shared.maven_version import MavenVersion


class BuildValidationError(RuntimeError):
    """Raised when a post-update project build validation fails."""


class BuildValidationManualUpdatesError(BuildValidationError):
    """Raised when validation cannot auto-isolate/fix breaking package updates."""


def _snippet(text: str, limit: int = 4000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _process_table() -> dict[int, tuple[int, str]]:
    """Return PID -> (PPID, command) for the current host."""
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,ppid=,command="],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return {}

    processes: dict[int, tuple[int, str]] = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        processes[pid] = (ppid, parts[2])
    return processes


def _gradle_daemon_pids():
    return {
        pid
        for pid, (_ppid, command) in _process_table().items()
        if "org.gradle.launcher.daemon.bootstrap.GradleDaemon" in command
    }


def _descendant_pids(
    roots: set[int],
    processes: dict[int, tuple[int, str]],
):
    descendants = set(roots)
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _command) in processes.items():
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return descendants


def _terminate_process_trees(roots: set[int]) -> None:
    if not roots:
        return
    processes = _process_table()
    pids = _descendant_pids(roots, processes)

    # Stop children before parents so Gradle workers cannot respawn while
    # their daemon is shutting down.
    ordered = sorted(
        pids,
        key=lambda pid: pid in roots,
    )

    for pid in ordered:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        surviving = {
            pid
            for pid in pids
            if _pid_exists(pid)
        }
        if not surviving:
            return
        time.sleep(0.1)

    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _run_build_command(
    cmd: list[str],
    cwd: str,
    timeout: int,
    label: str,
) -> subprocess.CompletedProcess:
    print(f"Validating updated project: {' '.join(cmd)}")
    is_gradle = any(
        "gradle" in Path(str(part)).name.lower()
        for part in cmd[:1]
    )
    gradle_daemons_before = (
        _gradle_daemon_pids()
        if is_gradle
        else set()
    )

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise BuildValidationError(
            f"{label} command not found: {cmd[0]!r}"
        ) from exc

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # Gradle launchers can leave daemons and test-worker JVMs behind.
        # Terminate the complete process group so later isolation trials do
        # not connect to a permanently busy daemon.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)

        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()

        if is_gradle:
            new_gradle_daemons = (
                _gradle_daemon_pids()
                - gradle_daemons_before
            )
            _terminate_process_trees(new_gradle_daemons)

        raise BuildValidationError(
            f"{label} timed out after {timeout}s"
        ) from exc

    result = subprocess.CompletedProcess(
        cmd,
        process.returncode,
        stdout,
        stderr,
    )

    if result.stdout:
        print(
            result.stdout,
            end="" if result.stdout.endswith("\n") else "\n",
        )
    if result.stderr:
        print(
            result.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
        )
    if result.returncode != 0:
        output = "\n".join(
            part
            for part in [result.stdout, result.stderr]
            if part
        )
        raise BuildValidationError(
            f"{label} failed with exit code {result.returncode}.\n"
            f"{_snippet(output)}"
        )
    return result
def _read_optional(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _restore_optional(path: Path, content: str | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(content, encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _clear_stale_manual_updates_csv(log_dir: str | None) -> None:
    """Remove a leftover build-validation-manual-updates.csv from a prior failed run.

    That file is only ever written on failure; a later run that succeeds (on the
    first attempt or after isolation) never rewrites or deletes it, so without
    this it silently keeps reporting an already-fixed run as needing manual
    intervention.
    """
    if not log_dir:
        return
    (Path(log_dir) / "build-validation-manual-updates.csv").unlink(missing_ok=True)


def _clear_stale_validation_csvs(log_dir: str | None) -> None:
    """Like _clear_stale_manual_updates_csv, but also drops a leftover
    build-validation-auto-fixes.csv.

    Use this specifically at a "build passed, no rollback of any kind was
    needed" success point (first attempt, timeout retry, ext-fix). Those
    paths never rewrite auto-fixes.csv themselves, so a prior run's rollback
    record survives untouched and report.py's CSV-presence fallback reads it
    as this run still needing attention (seen live: a repo whose build
    passed clean on the first try was reported Manual Update Required
    because an 18-hour-old auto-fixes.csv from an unrelated earlier run was
    still sitting in the same log_dir). Do NOT use this at an isolation
    success point (_write_success/_try_step_down) — those legitimately
    rewrite auto-fixes.csv with this run's own rollback record immediately
    after, so clearing it first is harmless there but this variant is not
    needed.
    """
    _clear_stale_manual_updates_csv(log_dir)
    if not log_dir:
        return
    (Path(log_dir) / "build-validation-auto-fixes.csv").unlink(missing_ok=True)


_MAX_INTERMEDIATE_REVERT_STEPS = 2

_STACK_FRAME_RE = re.compile(r"\bat ([\w$]+(?:\.[\w$]+)+)\(")

_FAILING_GRADLE_TASK_RE = re.compile(r"Execution failed for task '([^']+)'")


def _failing_gradle_task(output: str) -> str:
    match = _FAILING_GRADLE_TASK_RE.search(output or "")
    return match.group(1) if match else ""


_DAEMON_CRASH_SIGNATURES = (
    "gradle build daemon disappeared unexpectedly",
    "the daemon has disappeared",
)


def _is_transient_daemon_crash(failure_output: str) -> bool:
    """True when a build failure is Gradle's forked worker process getting
    killed (OOM, resource contention under parallel batch execution) rather
    than a real problem with the dependency update. --no-daemon only stops a
    *persistent* daemon from being reused across builds; Gradle still forks a
    single-use worker to execute the build, and that process can still be
    killed. Seen live: a jackson-databind 403 fix that had already been found
    and applied got reverted anyway because this crash — unrelated to the
    dependency change — was indistinguishable from a real build failure.
    """
    lowered = (failure_output or "").lower()
    return any(signature in lowered for signature in _DAEMON_CRASH_SIGNATURES)


def _extract_failing_tests(output: str) -> set[str]:
    """Extract Gradle per-test failure lines: 'SomeTest > someMethod() FAILED'.

    Task-level lines ('> Task :test FAILED') are excluded — they say a task
    failed, not which tests, and comparing at test granularity is what lets a
    pre-existing failure be told apart from a new one.
    """
    failing: set[str] = set()
    for match in re.finditer(r"(?m)^\s*(\S.*?) FAILED\s*$", output or ""):
        line = match.group(1).strip()
        if line.startswith("> Task"):
            continue
        if " > " in line:
            failing.add(line)
    return failing


def _is_preexisting_failure(baseline_failure: str, current_failure: str) -> bool:
    """True when the post-change failure is fully explained by the baseline.

    Requires the same failing Gradle task and that every currently failing
    test also failed at baseline. Compile errors and other failures without
    per-test detail never qualify — only test failures carry enough identity
    to attribute confidently.
    """
    baseline_task = _failing_gradle_task(baseline_failure)
    if not baseline_task or baseline_task != _failing_gradle_task(current_failure):
        return False
    baseline_tests = _extract_failing_tests(baseline_failure)
    current_tests = _extract_failing_tests(current_failure)
    if not baseline_tests or not current_tests:
        return False
    return current_tests <= baseline_tests


def _java_packages_in_output(output: str) -> set[str]:
    """Extract lowercase Java package prefixes from JVM stack trace frames.

    e.g. 'at ch.qos.logback.classic.LoggerContext.start(...)' → 'ch.qos.logback.classic'
    Stops at the first capitalized component (the class name boundary).
    """
    packages: set[str] = set()
    for m in _STACK_FRAME_RE.finditer(output):
        parts = m.group(1).split(".")
        pkg_parts = []
        for part in parts:
            if part and part[0].islower():
                pkg_parts.append(part)
            else:
                break
        if len(pkg_parts) >= 2:
            packages.add(".".join(pkg_parts))
    return packages


_STACK_FRAME_START_RE = re.compile(r"\bat [\w$.<>]+\(")


def _candidate_rank(output, package):
    if not output:
        return 0
    compact_package = package.lower()
    group = compact_package.split(":")[0] if ":" in compact_package else compact_package
    artifact = compact_package.split(":")[-1].split("/")[-1]
    lowered = output.lower()

    # The exception type/message — everything before the first "at X(" stack
    # frame — names what actually broke. The frames below it just show where
    # the failure surfaced, which is often shared/incidental machinery (a
    # test runner, a logging shim) rather than the broken dependency itself,
    # so a match there alone is much weaker evidence. Score the header at a
    # higher weight than the full text so a package named directly in the
    # message always outranks one merely visible somewhere in the trace.
    frame_match = _STACK_FRAME_START_RE.search(lowered)
    header = lowered[: frame_match.start()] if frame_match else lowered

    def _text_score(haystack: str, weight: int) -> int:
        points = 0
        if compact_package and compact_package in haystack:
            points += 10 * weight
        if len(artifact) >= 3 and artifact in haystack:
            points += 4 * weight
        for token in re.split(r"[^a-z0-9]+", artifact):
            if len(token) >= 5 and token in haystack:
                points += weight
        # Java error text uses dots (ch.qos.logback.core), never the Maven
        # hyphenated artifact id (logback-core), so this is the only check
        # that actually catches a group named directly in the message.
        if group and len(group) >= 5 and group in haystack:
            points += 8 * weight
        return points

    score = _text_score(header, 3) + _text_score(lowered, 1)

    # Weakest signal: a stack frame's Java package prefix merely matches the
    # Maven group ID somewhere in the trace, e.g. ch.qos.logback.classic →
    # ch.qos.logback. Kept separate and small — this is what previously let
    # every candidate sharing a group with incidental trace machinery
    # (e.g. all 13 org.springframework:* modules) tie for a high score.
    for pkg in _java_packages_in_output(output):
        if pkg.startswith(group) or group.startswith(pkg):
            score += 2
            break
    return score


def _ordered_candidates(candidates: list[dict[str, str]], output: str) -> list[dict[str, str]]:
    return sorted(
        candidates,
        key=lambda row: (
            _candidate_rank(output, row.get("package", "")),
            row.get("change_type", ""),
            row.get("package", ""),
        ),
        reverse=True,
    )
def _failure_implicates_candidate(candidates: list[dict[str, str]], output: str) -> bool:
    normalized = output.lower()
    if (
        "execution failed for task ':test'" in normalized
        or "there were failing tests" in normalized
    ):
        return True
    return any(_candidate_rank(output, row.get("package", "")) > 0 for row in candidates)




def _extract_gradle_blockers(output):
    blockers = []

    for match in re.finditer(r"Could not download (\S+)", output):
        filename = match.group(1).strip(".,;:()")
        for suffix in (".jar", ".pom"):
            if filename.endswith(suffix):
                filename = filename[: -len(suffix)]
                break

        version_start = None
        for idx, char in enumerate(filename):
            if char == "-" and idx + 1 < len(filename) and filename[idx + 1].isdigit():
                version_start = idx

        if version_start is None:
            blocker = filename
        else:
            blocker = f"{filename[:version_start]}:{filename[version_start + 1:]}"

        if blocker and blocker not in blockers:
            blockers.append(blocker)

    for match in re.finditer(r"Could not resolve (\S+)", output):
        blocker = match.group(1).strip(".,;:()")
        if blocker.lower() in {"all"}:
            continue
        if ":" not in blocker:
            continue
        if blocker and blocker not in blockers:
            blockers.append(blocker)

    return blockers


def _write_external_blockers(
    log_dir: str | None,
    ecosystem: str,
    failure_output: str,
    candidates: list[dict[str, str]],
) -> None:
    if not log_dir:
        return
    blockers = _extract_gradle_blockers(failure_output) if ecosystem == "gradle" else []
    if not blockers:
        blockers = ["unknown"]
    candidate_names = ", ".join(row.get("package", "") for row in candidates if row.get("package"))
    rows = [
        {
            "ecosystem": ecosystem,
            "blocker": blocker,
            "status": "external_build_blocker",
            "reason": "build failure did not mention any package changed by this run",
            "changed_candidates": candidate_names,
            "failure": _snippet(failure_output, 1000),
        }
        for blocker in blockers
    ]
    _write_csv(
        Path(log_dir) / "build-validation-external-blockers.csv",
        rows,
        ["ecosystem", "blocker", "status", "reason", "changed_candidates", "failure"],
    )
def _write_external_auto_fixes(
    log_dir: str | None,
    rows: list[dict[str, str]],
) -> None:
    if not log_dir or not rows:
        return
    _write_csv(
        Path(log_dir) / "build-validation-external-auto-fixes.csv",
        rows,
        [
            "dependency",
            "blocked_version",
            "forced_version",
            "status",
            "reason",
        ],
    )


def _run_candidate_trials(
    file_path: str,
    original_text: str,
    ordered_candidates: list[dict[str, str]],
    current_text: str,
    build_fn: Callable[[], None],
    revert_fn: Callable[[str, dict], str],
    log_dir: str | None,
    extra_snapshots: dict[Path, str | None],
    ext_fix_fn: Callable[[str], bool] | None = None,
    pre_check_fn: Callable[[], None] | None = None,
    enable_failure_isolation: bool = False,
    step_down_fn: Callable[[dict, str], str | None] | None = None,
    revert_to_version_fn: Callable[[str, dict, str], str | None] | None = None,
    confirm_fn: Callable[[], None] | None = None,
) -> None:
    """Find the smallest build-passing set of package rollbacks.

    The common single-culprit and greedy paths run first. If those are
    insufficient, a bounded exhaustive subset search explores interacting
    package combinations for up to the configured remediation budget.

    step_down_fn/revert_to_version_fn (optional) let a single culprit
    candidate be retried at one or two intermediate, still-non-vulnerable
    versions before accepting a full revert to the original vulnerable
    version — the difference between still fixing the CVE and giving up on
    it entirely. Both must be provided together; either omitted disables the
    ladder and falls back to today's binary revert-or-keep behavior.

    confirm_fn (optional) re-validates with the full build once a trial's
    (possibly lighter) build_fn passes, before that trial is accepted as a
    success — so build_fn can safely probe with a cheaper target (e.g. just
    "test") during the search without risking a false-positive success that
    the full build wouldn't actually pass. A confirm_fn failure is treated
    exactly like a build_fn failure: the search continues.
    """
    file_path_obj = Path(file_path)
    # Raised alongside gradle_timeout's 30s -> 150s default: enterprise Spring
    # multi-module builds routinely need 60-180s cold (--no-daemon, no warm
    # config cache) under batch-parallel contention, so a per-trial timeout
    # this size needs a proportionally larger search budget to still fit more
    # than one or two isolation trials before the deadline check bails.
    budget_seconds = max(
        30,
        int(
            os.environ.get(
                "PACKAGE_UPDATE_REMEDIATION_BUDGET_SECONDS",
                "600",
            )
        ),
    )
    deadline = time.monotonic() + budget_seconds
    tried: set[frozenset[str]] = set()
    trial_count = 0
    repeated_external_signature = ""
    repeated_external_count = 0
    stop_exhaustive = False

    def _failure_signature(failure: str) -> str:
        normalized = " ".join(str(failure).split())

        # The fast accessibility pre-check produces a stable list of
        # unrelated blocked coordinates.
        marker = "Accessibility pre-check failed"
        marker_index = normalized.find(marker)
        if marker_index >= 0:
            return normalized[marker_index:]

        # Gradle download/resolve failures can also identify a stable
        # external artifact blocker.
        blockers = sorted(set(_extract_gradle_blockers(failure)))
        if blockers:
            return "blocked:" + "|".join(blockers)

        # Generic compilation or test failures are not invariant
        # external blockers. Continue exhaustive subset exploration.
        return ""


    def _failure_mentions_candidates(
        failure: str,
        candidates: list[dict],
    ) -> bool:
        lowered = str(failure).lower()

        for candidate in candidates:
            package = str(
                candidate.get("package", "")
            ).strip().lower()
            artifact = package.split(":")[-1]

            # Full Maven/npm coordinates are sufficiently specific.
            if ":" in package and package in lowered:
                return True

            # Avoid matching short names such as "A" inside words such as
            # "Accessibility". Require a meaningful artifact token and
            # token boundaries.
            if len(artifact) >= 3:
                artifact_pattern = (
                    r"(?<![a-z0-9_.-])"
                    + re.escape(artifact)
                    + r"(?![a-z0-9_.-])"
                )
                if re.search(artifact_pattern, lowered):
                    return True

        return False


    def _candidate_id(candidate: dict) -> str:
        return "|".join(
            (
                str(candidate.get("package", "")),
                str(candidate.get("change_type", "")),
                str(candidate.get("old", "")),
                str(candidate.get("new", "")),
            )
        )

    def _revert_key(reverts: list[dict]) -> frozenset:
        return frozenset(
            _candidate_id(candidate)
            for candidate in reverts
        )

    def _write_state(state_text: str) -> None:
        file_path_obj.write_text(state_text, encoding="utf-8")
        for snapshot_path, content in extra_snapshots.items():
            _restore_optional(snapshot_path, content)

    def _apply_reverts(reverts: list[dict]) -> str:
        state_text = current_text
        for candidate in reverts:
            state_text = revert_fn(state_text, candidate)
        return state_text
    def _try_build() -> None:
        if pre_check_fn:
            pre_check_fn()
        build_fn()
        if confirm_fn:
            confirm_fn()

    def _trial(
        reverts: list[dict],
        label: str,
        allow_ext_fix: bool = False,
    ) -> tuple[bool, str]:
        nonlocal trial_count
        nonlocal repeated_external_signature
        nonlocal repeated_external_count
        nonlocal stop_exhaustive

        key = _revert_key(reverts)
        if key in tried:
            return False, ""
        tried.add(key)

        if time.monotonic() >= deadline:
            return False, "budget exhausted"

        trial_count += 1
        packages = ", ".join(
            candidate.get("package", "")
            for candidate in reverts
        )
        print(
            f"{label}: trial {trial_count}, reverting "
            f"{len(reverts)} package(s): {packages}"
        )
        _write_state(_apply_reverts(reverts))

        try:
            _try_build()
            return True, ""
        except BuildValidationError as exc:
            failure = str(exc)

            if (
                allow_ext_fix
                and ext_fix_fn
                and _extract_gradle_blockers(failure)
                and ext_fix_fn(failure)
            ):
                return True, ""

            signature = _failure_signature(failure)
            unrelated = not _failure_mentions_candidates(
                failure,
                reverts,
            )

            if unrelated and signature:
                if signature == repeated_external_signature:
                    repeated_external_count += 1
                else:
                    repeated_external_signature = signature
                    repeated_external_count = 1

                if repeated_external_count >= 3:
                    stop_exhaustive = True
                    _dbg(
                        log_dir,
                        "stopping isolation search: identical "
                        "non-candidate blocker repeated in "
                        f"{repeated_external_count} trials: "
                        f"{signature[-500:]}",
                    )
            else:
                repeated_external_signature = ""
                repeated_external_count = 0

            _dbg(
                log_dir,
                f"{label} failed for [{packages}]: "
                f"{failure[-600:]}",
            )
            return False, failure

    def _write_success(reverts: list[dict], reason: str) -> None:
        _write_state(_apply_reverts(reverts))
        _clear_stale_manual_updates_csv(log_dir)
        rows = [
            {
                **candidate,
                "status": "auto_rolled_back",
                "reason": reason,
            }
            for candidate in reverts
        ]
        if log_dir and rows:
            _write_csv(
                Path(log_dir) / "build-validation-auto-fixes.csv",
                rows,
                [
                    "package",
                    "change_type",
                    "old",
                    "new",
                    "status",
                    "reason",
                ],
            )

    def _try_step_down(candidate: dict) -> bool:
        """Try a short ladder of intermediate, still-non-vulnerable versions
        for `candidate` before its single-package trial falls back to a full
        revert. Returns True (and leaves the state written) on success.
        """
        nonlocal trial_count
        if not (step_down_fn and revert_to_version_fn):
            return False

        last_version = candidate.get("new", "")
        for _ in range(_MAX_INTERMEDIATE_REVERT_STEPS):
            if time.monotonic() >= deadline:
                return False
            next_version = step_down_fn(candidate, last_version)
            if not next_version or next_version == last_version:
                return False

            stepped_text = revert_to_version_fn(current_text, candidate, next_version)
            if stepped_text is None:
                return False

            trial_count += 1
            print(
                f"Intermediate-version isolation: trial {trial_count}, "
                f"stepping {candidate.get('package', '')} down to {next_version} "
                f"(originally targeted {candidate.get('new', '')})"
            )
            _write_state(stepped_text)
            try:
                _try_build()
            except BuildValidationError as exc:
                _dbg(
                    log_dir,
                    f"Intermediate-version isolation failed for "
                    f"[{candidate.get('package', '')}@{next_version}]: "
                    f"{str(exc)[-600:]}",
                )
                last_version = next_version
                continue

            _clear_stale_manual_updates_csv(log_dir)
            if log_dir:
                _write_csv(
                    Path(log_dir) / "build-validation-auto-fixes.csv",
                    [{
                        "package": candidate.get("package", ""),
                        "change_type": candidate.get("change_type", ""),
                        "old": candidate.get("new", ""),
                        "new": next_version,
                        "status": "stepped_down",
                        "reason": (
                            "build passed at an intermediate non-vulnerable version "
                            f"after {candidate.get('new', '')} broke the build"
                        ),
                    }],
                    ["package", "change_type", "old", "new", "status", "reason"],
                )
            print(
                f"Isolation complete: stepped {candidate.get('package', '')} "
                f"down to {next_version} (still resolves the flagged CVE)."
            )
            return True

        return False

    def _write_failure(reason: str) -> None:
        # Symmetric to _clear_stale_manual_updates_csv: a failed run must not
        # leave auto-fix rows from an earlier successful pass in its logs —
        # everything was just restored to the original text, so any prior
        # auto_rolled_back rows no longer describe the on-disk state.
        if log_dir:
            (Path(log_dir) / "build-validation-auto-fixes.csv").unlink(missing_ok=True)
        manual_rows = [
            {
                **candidate,
                "status": "manual_update_required",
                "reason": reason,
            }
            for candidate in ordered_candidates
        ]
        _write_state(original_text)
        if log_dir:
            _write_csv(
                Path(log_dir) / "build-validation-manual-updates.csv",
                manual_rows,
                [
                    "package",
                    "change_type",
                    "old",
                    "new",
                    "status",
                    "reason",
                ],
            )

    if not enable_failure_isolation:
        _write_failure(
            "build validation failed and failure isolation disabled"
        )
        print(
            "Build validation failed; rollback isolation is disabled."
        )
        raise BuildValidationManualUpdatesError(
            "Build validation failed. Failure isolation disabled."
        )

    # Phase 1: quickly handle the common single-package culprit.
    for candidate in ordered_candidates:
        if _try_step_down(candidate):
            return
        passed, _ = _trial(
            [candidate],
            "Single-package isolation",
        )
        if passed:
            _write_success(
                [candidate],
                "build passed after single-package rollback",
            )
            print(
                "Isolation complete: reverted "
                f"{candidate['package']}."
            )
            return
        if stop_exhaustive:
            break

    # Phase 2: greedily obtain any passing state.
    print(
        "Single-package rollback did not isolate the failure; "
        "trying greedy accumulation..."
    )
    greedy_reverts: list[dict[str, str]] = []
    greedy_passed = False

    for candidate in ordered_candidates:
        greedy_reverts.append(candidate)
        passed, _ = _trial(
            list(greedy_reverts),
            "Greedy isolation",
            allow_ext_fix=True,
        )
        if passed:
            greedy_passed = True
            break

        if stop_exhaustive:
            break
        if stop_exhaustive:
            break

    best_reverts = list(greedy_reverts) if greedy_passed else None

    # Phase 3: exhaustive best-first subset search. Search by rollback count,
    # so the first passing combination is globally minimal by number of
    # reverted packages within the explored budget.
    candidate_count = len(ordered_candidates)
    upper_size = (
        len(best_reverts) - 1
        if best_reverts is not None
        else candidate_count - 1
    )

    if (
        upper_size >= 2
        and time.monotonic() < deadline
        and not stop_exhaustive
    ):
        print(
            "Starting exhaustive interaction search with a "
            f"{budget_seconds}s remediation budget..."
        )

        for subset_size in range(2, upper_size + 1):
            if time.monotonic() >= deadline:
                break

            for subset in combinations(
                ordered_candidates,
                subset_size,
            ):
                if (
                    time.monotonic() >= deadline
                    or stop_exhaustive
                ):
                    break

                reverts = list(subset)
                passed, _ = _trial(
                    reverts,
                    "Exhaustive isolation",
                    allow_ext_fix=True,
                )
                if passed:
                    best_reverts = reverts
                    break

            if (
                best_reverts is not None
                and len(best_reverts) == subset_size
            ):
                break

    if best_reverts is None:
        budget_exhausted = time.monotonic() >= deadline
        if stop_exhaustive:
            reason = (
                "build failed because repeated isolation trials "
                "encountered the same non-candidate blocker"
            )
        elif budget_exhausted:
            reason = (
                "build failed after exhaustive isolation budget "
                "was exhausted"
            )
        else:
            reason = (
                "build failed and exhaustive isolation found "
                "no safe subset"
            )
        _write_failure(reason)
        print(
            f"Validation failed after {trial_count} isolation trial(s); "
            f"restored {file_path}."
        )
        raise BuildValidationManualUpdatesError(
            "Build validation failed. Exhaustive isolation could not "
            "find a build-passing update subset."
        )

    # Phase 4: rescue pass. Remove unnecessary reverts while preserving the
    # passing build. This also protects against a budget-limited exhaustive
    # search returning a non-minimal combination.
    print(
        f"Passing state found with {len(best_reverts)} revert(s); "
        "running rescue pass..."
    )
    final_reverts = list(best_reverts)

    for candidate in reversed(list(best_reverts)):
        if time.monotonic() >= deadline:
            break

        reduced = [
            row
            for row in final_reverts
            if _candidate_id(row) != _candidate_id(candidate)
        ]
        passed, _ = _trial(
            reduced,
            "Rescue isolation",
            allow_ext_fix=True,
        )
        if passed:
            final_reverts = reduced
            print(
                f"Rescued {candidate['package']} - keeping its update."
            )

    reason = (
        "build passed after exhaustive subset isolation and rescue"
        if trial_count > len(ordered_candidates) * 2
        else "build passed after rollback isolation and rescue"
    )
    _write_success(final_reverts, reason)

    elapsed = budget_seconds - max(
        0,
        int(deadline - time.monotonic()),
    )
    print(
        f"Isolation complete: {len(final_reverts)} package(s) "
        f"reverted after {trial_count} trial(s) in ~{elapsed}s."
    )

_CANT_RESOLVE_RE = re.compile(r"Could not resolve ([\w.]+:[\w.-]+:[^\s,.()]+)")
_REQUIRED_BY_GA_RE = re.compile(r"\b([\w][\w.-]*\.[\w.-]+:[\w][\w.-]+)(?::[\w.+\-]+)?")


def _parse_required_by(output: str) -> dict[str, set[str]]:
    """Map blocked 'group:artifact' → parent 'group:artifact' keys from Gradle's Required by chain."""
    result: dict[str, set[str]] = {}
    for m in _CANT_RESOLVE_RE.finditer(output):
        parts = m.group(1).split(":")
        if len(parts) < 2:
            continue
        blocked_key = f"{parts[0]}:{parts[1]}"
        window = output[m.end(): m.end() + 600]
        if "Required by:" not in window:
            continue
        rb_text = window[window.index("Required by:") + len("Required by:"): ]
        parents: set[str] = set()
        for ga_m in _REQUIRED_BY_GA_RE.finditer(rb_text[:400]):
            ga = ga_m.group(1)
            if ga != blocked_key:
                parents.add(ga)
        if parents:
            result.setdefault(blocked_key, set()).update(parents)
    return result


def _artifactory_auth_from_env() -> tuple[str, str] | None:
    username = os.environ.get("ARTIFACTORY_USERNAME", "")
    password = os.environ.get("ARTIFACTORY_PASSWORD", "")
    return (username, password) if username else None


def _dbg(log_dir: str | None, msg: str) -> None:
    print(f"  [ext-fix] {msg}")
    if log_dir:
        import os as _os

        # Appended across every run against this log_dir, with no run
        # boundary otherwise visible in the file — a repo re-validated
        # repeatedly in one day (a common pattern here) produces one long
        # undifferentiated trace where old and current-run entries are
        # indistinguishable without this.
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_os.path.join(log_dir, "build-validation-debug.txt"), "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")


def _try_fix_external_gradle_blockers(
    build_file: str,
    current_text: str,
    failure_output: str,
    gradle_cmd: str,
    timeout: int,
    log_dir: str | None,
    auth: tuple[str, str] | None = None,
    xray_host: str | None = None,
    base_url: str | None = None,
    changes: list[dict] | None = None,
    handled: set[tuple[str, str, str]] | None = None,
    repo_urls: list[str] | None = None,
) -> bool:
    """Try to remediate every 403-blocked Gradle artifact in build output.

    This is intentionally not limited to remediation/candidate dependencies. It mirrors
    Node's block checker behavior: any resolved dependency that Gradle reports as
    blocked is eligible for safe fallback selection before candidate rollback is
    attempted.

    Each round:
    - parse all blocked Maven GAVs from the latest Gradle failure
    - find an accessible, Xray-clean fallback with forward-then-backward logic
    - rewrite a direct/strict declaration when present
    - also add a force for classpath/transitive safety
    - rerun gradle build
    """

    from output.gradle import write_dependency_substitutions, write_resolution_forces
    from parsers.gradle import (
        find_accessible_version,
        get_available_versions,
        parse_gradle_deps,
        parse_gradle_repositories,
    )
    from parsers.gradle_tree import _parse_blocked_packages

    build_path = Path(build_file)
    original_trial_text = current_text
    if auth is None:
        auth = _artifactory_auth_from_env()
    changed_keys = {row.get("dependency", "") for row in (changes or [])}
    auto_rows: list[dict[str, str]] = []
    if handled is None:
        handled = set()
    last_failure: str = failure_output
    any_forces_written: bool = False

    for _round in range(1, 11):
        blocked = _parse_blocked_packages(failure_output)
        blocked = [
            row
            for row in blocked
            if (row[0], row[1], row[2]) not in handled
        ]
        _dbg(log_dir, f"round {_round}: {len(blocked)} new blocked packages")
        if not blocked:
            if any_forces_written:
                # 403s resolved; remaining failure is non-403 — keep forces applied
                # so the caller can run candidate rollback on the current state.
                _dbg(log_dir, "403s cleared; returning partial-fix state for candidate rollback")
                return last_failure  # type: ignore[return-value]
            build_path.write_text(original_trial_text, encoding="utf-8")
            return False

        required_by = _parse_required_by(failure_output)
        text = build_path.read_text(encoding="utf-8")
        deps = parse_gradle_deps(text)
        direct_by_key = {f"{dep.group}:{dep.artifact}": dep for dep in deps}
        # Prefer the Gradle-evaluated repo URLs threaded in from resolve_tree —
        # a regex parse of the build file returns unresolved property
        # references like "${ARTIFACTORY_SOURCE}" verbatim, which then breaks
        # every accessibility probe run against them. Falls back to the regex
        # parse (then base_url) when the caller didn't have a resolved list.
        build_repo_urls = repo_urls or parse_gradle_repositories(text)
        force_entries: list[dict[str, str]] = []
        found_any_fix = False

        for group, artifact, version, _repo_url in blocked:
            handled.add((group, artifact, version))
            key = f"{group}:{artifact}"
            current = MavenVersion.parse(version)
            if current is None:
                _dbg(log_dir, f"{key}:{version} — unparseable version, skipping")
                continue

            # If this blocked package is a transitive of a dependency we changed,
            # skip forcing it here — the candidate rollback will handle the parent.
            if key not in direct_by_key and changed_keys:
                parents = required_by.get(key, set())
                if parents & changed_keys:
                    _dbg(log_dir, f"{key}:{version} — transitive of changed {parents & changed_keys}, deferring to candidate rollback")
                    continue

            # Use the URLs the build file declares for accessibility checking — not
            # repo_url from Gradle's error output, which may be Maven Central or another
            # public mirror unreachable from this host.
            check_url = (build_repo_urls[0] if build_repo_urls else None) or base_url or os.environ.get("ARTIFACTORY_SOURCE", "").rstrip("/")
            if not check_url:
                _dbg(log_dir, f"{key}:{version} — no check_url, skipping")
                continue

            # Use base_url (virtual/aggregated repo) for version listing so maven-metadata.xml
            # is always available. Fall back to check_url if base_url returns nothing.
            meta_url = base_url or check_url
            _dbg(log_dir, f"{key}:{version} — listing from {meta_url}, checking access via {', '.join(build_repo_urls) if build_repo_urls else check_url}")
            available, _error = get_available_versions(group, artifact, meta_url, auth, timeout)
            if not available:
                available, _error = get_available_versions(group, artifact, check_url, auth, timeout)
            _dbg(log_dir, f"{key}:{version} — {len(available)} versions available{(': ' + _error) if not available else ''}")
            if not available:
                continue

            forced_version = find_accessible_version(
                group,
                artifact,
                current,
                available,
                check_url,
                auth,
                timeout,
                xray_host=xray_host,
                repo_urls=build_repo_urls or None,
                log_dir=log_dir,
            )
            _dbg(log_dir, f"{key}:{version} — find_accessible_version -> {forced_version!r}")
            if forced_version is None or forced_version == version:
                continue

            direct_dep = direct_by_key.get(key)
            if direct_dep is not None:
                replacement = direct_dep.original.replace(
                    direct_dep.version,
                    forced_version,
                    1,
                )
                text = text.replace(direct_dep.original, replacement, 1)

            force_entries.append(
                {
                    "dependency": key,
                    "old_version": version,
                    "new_version": forced_version,
                    "minimum_required": forced_version,
                }
            )
            auto_rows.append(
                {
                    "dependency": key,
                    "blocked_version": version,
                    "forced_version": forced_version,
                    "status": "auto_forced_blocked_gradle_artifact",
                    "reason": (
                        "project build passed after replacing a blocked Gradle "
                        "artifact with a non-vulnerable accessible fallback"
                    ),
                }
            )
            found_any_fix = True

        if not found_any_fix:
            build_path.write_text(original_trial_text, encoding="utf-8")
            return False

        text = write_resolution_forces(text, force_entries)
        text = write_dependency_substitutions(text, force_entries)
        build_path.write_text(text, encoding="utf-8")
        any_forces_written = True

        build_passed = False
        for attempt in (1, 2):
            # After a crash, the retry starts a cold daemon (no warm JIT/config
            # cache) under the same host contention that likely caused the
            # crash — reusing the original tight timeout here previously just
            # traded one failure mode for another (seen live: retry attempt
            # ran ~32s and hit a plain "timed out after 30s" instead of
            # recovering). Give the retry the same generous floor the
            # top-level post-crash retry already uses.
            attempt_timeout = timeout if attempt == 1 else max(300, timeout * 3)
            try:
                validate_gradle_project(build_file, gradle_cmd=gradle_cmd, timeout=attempt_timeout)
            except BuildValidationError as exc:
                failure_output = str(exc)
                # A crashed Gradle worker process (OOM, resource contention
                # under parallel batch execution) is unrelated to whether this
                # round's fix is correct — seen live losing an
                # already-successful jackson-databind 403 fix to a full
                # revert. --no-daemon only stops daemon *reuse*; a forked
                # single-use worker can still be killed. Retry once before
                # blaming this round's fix.
                if attempt == 1 and _is_transient_daemon_crash(failure_output):
                    _dbg(
                        log_dir,
                        f"round {_round} build hit a transient daemon crash; retrying once with a longer timeout",
                    )
                    continue
                last_failure = failure_output
                _dbg(log_dir, f"round {_round} build still failed: {failure_output[-1200:]}")
                break
            else:
                build_passed = True
                break

        if not build_passed:
            continue

        _write_external_auto_fixes(log_dir, auto_rows)
        print(
            "Build validation passed after fixing blocked Gradle artifact(s): "
            + ", ".join(
                f"{row['dependency']}:{row['forced_version']}"
                for row in auto_rows
            )
        )
        return True

    if any_forces_written:
        _dbg(log_dir, "round limit reached; returning partial-fix state for candidate rollback")
        return last_failure  # type: ignore[return-value]
    build_path.write_text(original_trial_text, encoding="utf-8")
    return False






def _make_gradle_pre_check_fn(
    build_file: str,
    repo_urls: list[str],
    base_url: str | None,
    auth: tuple[str, str] | None,
    timeout: int,
    baseline_text: str | None = None,
) -> Callable[[], None]:
    """Return a closure that HTTP-checks changed Gradle deps via JFrog.

    Re-reads the build file on every call so it reflects whatever revert has just been
    applied. Parallel HEAD requests — typically under 2 seconds. Raises
    BuildValidationError if any declared dep is inaccessible, skipping the full build.
    """
    from concurrent.futures import ThreadPoolExecutor

    from parsers.gradle import (
        normalize_gradle_version_for_probe,
        parse_gradle_deps,
    )
    from registry.maven import version_accessible

    check_urls = list(dict.fromkeys((repo_urls or []) + ([base_url] if base_url else [])))
    baseline_versions: dict[str, str] = {}
    if baseline_text is not None:
        for dep in parse_gradle_deps(baseline_text):
            probe_version = normalize_gradle_version_for_probe(dep.version)
            if probe_version is not None:
                baseline_versions[f"{dep.group}:{dep.artifact}"] = probe_version

    def _pre_check() -> None:
        if not check_urls:
            return
        text = Path(build_file).read_text(encoding="utf-8")
        deps = parse_gradle_deps(text)
        if not deps:
            return

        def _check(dep):
            probe_version = normalize_gradle_version_for_probe(
                dep.version
            )
            if probe_version is None:
                # Let Gradle resolve ranges, dynamic versions, and
                # variables. They are not valid literal Maven paths.
                return dep, None, None

            dependency_key = f"{dep.group}:{dep.artifact}"
            if baseline_versions.get(dependency_key) == probe_version:
                # This exact dependency existed before remediation. It is
                # not attributable to the proposed update, so let Gradle
                # handle it instead of rejecting every isolation trial.
                return dep, probe_version, None

            accessible = any(
                version_accessible(
                    dep.group,
                    dep.artifact,
                    probe_version,
                    url,
                    auth,
                    timeout,
                )
                for url in check_urls
            )
            return dep, probe_version, accessible
        blocked: list[str] = []
        with ThreadPoolExecutor(
            max_workers=min(8, len(deps))
        ) as pool:
            for dep, probe_version, accessible in pool.map(
                _check,
                deps,
            ):
                if accessible is False:
                    blocked.append(
                        f"{dep.group}:{dep.artifact}:"
                        f"{probe_version}"
                    )

        if blocked:
            raise BuildValidationError(
                "Accessibility pre-check failed — blocked: " + ", ".join(blocked)
            )

    return _pre_check


def validate_or_rollback(
    file_path: str,
    original_text: str,
    current_text: str,
    failure_output: str,
    candidates: list[dict[str, str]],
    build_fn: Callable[[], None],
    revert_fn: Callable[[str, dict], str],
    log_dir: str | None,
    ecosystem: str,
    extra_snapshots: dict[Path, str | None] | None = None,
    pre_check_fn: Callable[[], None] | None = None,
    ext_fix_fn: Callable[[str], bool] | None = None,
    skip_implicate_check: bool = False,
    enable_failure_isolation: bool = False,
    step_down_fn: Callable[[dict, str], str | None] | None = None,
    revert_to_version_fn: Callable[[str, dict, str], str | None] | None = None,
    confirm_fn: Callable[[], None] | None = None,
) -> None:
    """Shared rollback orchestration for all ecosystems.

    Callers handle ecosystem-specific pre-processing (proactive dep-tree check,
    ext-fix for 403s) and provide the resulting state. This function handles the
    "does the failure implicate our changes?" guard then delegates to
    _run_candidate_trials with the supplied pre_check_fn and ext_fix_fn.

    skip_implicate_check=True should be passed by Gradle when ext-fix partially
    resolved 403s (ext_fix_result is str) — in that case the failure_output has
    already been updated to a non-403 error and rollback must proceed regardless.
    """
    file_path_obj = Path(file_path)
    snapshots = extra_snapshots or {}
    ordered = _ordered_candidates(candidates, failure_output)

    if ordered and not skip_implicate_check and not _failure_implicates_candidate(ordered, failure_output):
        blockers = _extract_gradle_blockers(failure_output) if ecosystem == "gradle" else []

        # Only treat as an external blocker when we have a concrete blocker that
        # is not one of the packages changed by this run. Generic build failures
        # should continue into rollback isolation.
        if blockers:
            file_path_obj.write_text(original_text, encoding="utf-8")
            for path, content in snapshots.items():
                _restore_optional(path, content)
            _write_external_blockers(log_dir, ecosystem, failure_output, ordered)
            print(f"Validation failed due to a non-candidate build blocker; restored {file_path}")
            raise BuildValidationManualUpdatesError(
                "Build validation failed before implicating a package changed by this run. "
                "External blocker details were logged."
            )

    _run_candidate_trials(
        file_path,
        original_text,
        ordered,
        current_text,
        build_fn,
        revert_fn,
        log_dir,
        snapshots,
        ext_fix_fn=ext_fix_fn,
        pre_check_fn=pre_check_fn,
        enable_failure_isolation=enable_failure_isolation,
        step_down_fn=step_down_fn,
        revert_to_version_fn=revert_to_version_fn,
        confirm_fn=confirm_fn,
    )


def _remove_key_recursive(value: Any, target: str) -> None:
    if not isinstance(value, dict):
        return
    value.pop(target, None)
    for child in list(value.values()):
        _remove_key_recursive(child, target)


def _restore_key_recursive(current: Any, original: Any, target: str) -> None:
    if not isinstance(current, dict):
        return
    if isinstance(original, dict) and target in original:
        current[target] = deepcopy(original[target])
    elif target in current:
        current.pop(target, None)

    keys = set(current)
    if isinstance(original, dict):
        keys.update(original)
    for key in keys:
        cur_child = current.get(key)
        orig_child = original.get(key) if isinstance(original, dict) else None
        if isinstance(cur_child, dict) or isinstance(orig_child, dict):
            if key not in current or not isinstance(current.get(key), dict):
                current[key] = {}
            _restore_key_recursive(current[key], orig_child, target)
            if current.get(key) == {} and not (isinstance(orig_child, dict) and orig_child):
                current.pop(key, None)


def _revert_node_package(
    current: dict[str, Any], original: dict[str, Any], package: str
) -> dict[str, Any]:
    trial = deepcopy(current)
    for section in [
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
        "overrides",
        "resolutions",
    ]:
        cur_section = trial.get(section)
        orig_section = original.get(section)
        if not isinstance(cur_section, dict):
            continue
        if isinstance(orig_section, dict) and package in orig_section:
            cur_section[package] = deepcopy(orig_section[package])
        else:
            cur_section.pop(package, None)
        if section in {"overrides", "resolutions"}:
            _restore_key_recursive(
                cur_section, orig_section if isinstance(orig_section, dict) else {}, package
            )
            _remove_key_recursive(cur_section, package)
            if isinstance(orig_section, dict):
                _restore_key_recursive(cur_section, orig_section, package)
        if cur_section == {} and not isinstance(orig_section, dict):
            trial.pop(section, None)
    return trial


def _node_candidates(
    direct_changes: list[dict[str, str]] | None,
    override_changes: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for row in direct_changes or []:
        package = row.get("package", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "direct",
                "old": row.get("old_spec", ""),
                "new": row.get("new_spec", ""),
            }
        )
        seen.add(package)
    for row in override_changes or []:
        package = row.get("package", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "override",
                "old": row.get("old_override", ""),
                "new": row.get("new_override", ""),
            }
        )
        seen.add(package)
    return rows


def _revert_python_dep(text: str, candidate: dict, file_type: str) -> str:
    from parsers.python import update_python_dependency_text
    return update_python_dependency_text(
        text,
        [{"line_index": candidate["line_index"], "new_version": candidate["old"]}],
        file_type=file_type,
    )


def validate_node_project(
    package_json_path: str,
    npm_cmd: str = "npm",
    timeout: int = 600,
) -> None:
    """Validate an updated Node project by installing and running its build script.

    The install step verifies dependency resolution and refreshes the lockfile.
    If package.json has a scripts.build entry, npm run build is executed too.
    """

    pkg_path = Path(package_json_path)
    project_dir = str(pkg_path.resolve().parent)
    package_json = json.loads(pkg_path.read_text(encoding="utf-8"))
    _run_build_command(
        [npm_cmd, "install", "--no-audit", "--no-fund"],
        project_dir,
        timeout,
        "npm install validation",
    )

    scripts: dict[str, Any] = package_json.get("scripts", {})
    if isinstance(scripts, dict) and scripts.get("build"):
        _run_build_command(
            [npm_cmd, "run", "build"],
            project_dir,
            timeout,
            "npm build validation",
        )
    else:
        print("No npm build script found; npm install validation completed.")


def validate_node_project_or_rollback(
    package_json_path: str,
    original_package_json: str,
    npm_cmd: str = "npm",
    timeout: int = 600,
    direct_changes: list[dict[str, str]] | None = None,
    override_changes: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
    enable_failure_isolation: bool = False,
) -> None:
    pkg_path = Path(package_json_path)
    project_dir = pkg_path.resolve().parent
    lock_paths = [
        project_dir / "package-lock.json",
        project_dir / "npm-shrinkwrap.json",
    ]
    lock_snapshots = {path: _read_optional(path) for path in lock_paths}

    try:
        validate_node_project(package_json_path, npm_cmd=npm_cmd, timeout=timeout)
        _clear_stale_validation_csvs(log_dir)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    original_pkg = json.loads(original_package_json)
    current_text = pkg_path.read_text(encoding="utf-8")

    validate_or_rollback(
        package_json_path,
        original_package_json,
        current_text,
        failure_output,
        _node_candidates(direct_changes, override_changes),
        build_fn=lambda: validate_node_project(package_json_path, npm_cmd=npm_cmd, timeout=timeout),
        revert_fn=lambda text, c: json.dumps(
            _revert_node_package(json.loads(text), original_pkg, c["package"]), indent=2
        ) + "\n",
        log_dir=log_dir,
        ecosystem="node",
        extra_snapshots=lock_snapshots,
        enable_failure_isolation=enable_failure_isolation,
    )


_GRADLE_TEST_LOGGING_INIT = """\
allprojects {
    tasks.withType(Test).configureEach {
        testLogging {
            exceptionFormat 'full'
            showStackTraces true
            showCauses true
        }
    }
}
"""


def _gradle_init_script_path() -> str:
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "pkg_update_gradle_logging.gradle")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_GRADLE_TEST_LOGGING_INIT)
    return path


def validate_gradle_project(
    build_file: str,
    gradle_cmd: str,
    timeout: int = 600,
    tasks: str = "build",
) -> None:
    """Validate an updated Gradle project by running gradle/gradlew <tasks>.

    tasks defaults to the full "build" lifecycle. Isolation trials pass a
    lighter target (e.g. "test") to skip packaging/coverage tasks that don't
    affect whether a candidate rollback actually fixes the failure — the
    winning trial is re-confirmed with the full "build" before being accepted.
    """
    project_dir = os.path.dirname(os.path.abspath(build_file))
    _run_build_command(
        [
            gradle_cmd,
            tasks,
            "--no-daemon",
            # Isolation trials must not share a reusable daemon. A timed-out
            # build can otherwise leave that daemon BUSY and cause every
            # subsequent candidate trial to hang.
            "--init-script",
            _gradle_init_script_path(),
        ],
        project_dir,
        timeout,
        "Gradle build validation",
    )


def _gradle_baseline_failure(
    build_path: Path,
    original_text: str,
    current_text: str,
    gradle_cmd: str,
    timeout: int,
) -> str | None:
    """Build once with the pre-remediation file; return its failure text, or
    None when the baseline passes (meaning the current failure is ours)."""
    if original_text == current_text:
        return None
    build_path.write_text(original_text, encoding="utf-8")
    try:
        validate_gradle_project(
            str(build_path), gradle_cmd=gradle_cmd, timeout=timeout,
        )
        return None
    except BuildValidationError as exc:
        return str(exc)
    finally:
        build_path.write_text(current_text, encoding="utf-8")


def capture_gradle_build_logs(
    build_path: Path,
    original_text: str,
    current_text: str,
    gradle_cmd: str,
    timeout: int,
    log_dir: str,
) -> None:
    """Opt-in diagnostic (cfg.capture_build_logs): run two explicit gradle
    builds -- one against the pre-remediation file, one against the
    already-written post-remediation file -- purely to leave clean
    build-log-before.txt/build-log-after.txt artifacts. An extra full build
    per repo; meant for verification runs, not production batches, hence
    gated behind a config flag rather than always-on.
    """
    cmd = [gradle_cmd, "build", "--no-daemon", "--init-script", _gradle_init_script_path()]
    cwd = str(build_path.resolve().parent)

    def _run_once(build_timeout: int) -> tuple[bool, str]:
        try:
            result = _run_build_command(cmd, cwd, build_timeout, "build log capture")
            return True, "\n".join(part for part in (result.stdout, result.stderr) if part)
        except BuildValidationError as exc:
            return False, str(exc)

    def _run_with_retry() -> str:
        passed, output = _run_once(timeout)
        # Same transient-worker-crash retry _run_candidate_trials already
        # applies elsewhere -- without it this diagnostic build would
        # reintroduce the exact false "failure" a crashed (not broken) worker
        # produces under batch memory contention.
        if not passed and _is_transient_daemon_crash(output):
            _, output = _run_once(max(300, timeout * 3))
        return output

    if original_text != current_text:
        build_path.write_text(original_text, encoding="utf-8")
        try:
            before_output = _run_with_retry()
        finally:
            build_path.write_text(current_text, encoding="utf-8")
        with contextlib.suppress(Exception):
            Path(log_dir, "build-log-before.txt").write_text(before_output, encoding="utf-8")

    after_output = _run_with_retry()
    with contextlib.suppress(Exception):
        Path(log_dir, "build-log-after.txt").write_text(after_output, encoding="utf-8")


def _record_preexisting_failure(log_dir: str | None, baseline_failure: str) -> None:
    if not log_dir:
        return
    task = _failing_gradle_task(baseline_failure)
    rows = [
        {
            "task": task,
            "test": test,
            "status": "preexisting_test_failure",
            "reason": "test already failed before remediation; updates were kept",
        }
        for test in sorted(_extract_failing_tests(baseline_failure))
    ]
    _write_csv(
        Path(log_dir) / "build-validation-preexisting-failures.csv",
        rows,
        ["task", "test", "status", "reason"],
    )


def _remove_gradle_force(build_text: str, dependency: str, version: str) -> str:
    target = f"{dependency}:{version}"
    lines = []
    for line in build_text.splitlines():
        if "force " in line and target in line:
            continue
        lines.append(line)
    return "\n".join(lines) + ("\n" if build_text.endswith("\n") else "")


def _revert_gradle_package(
    current_text,
    changes,
    force_entries,
    dependency,
):
    from output.gradle import (
        is_spring_boot_managed_project,
        spring_boot_managed_property,
        write_spring_boot_managed_properties,
        write_spring_boot_plugin_version,
    )

    text = current_text

    for row in changes or []:
        if row.get("dependency") != dependency:
            continue

        replacement = row.get("replacement", "")
        original = row.get("original", "")

        if replacement and original:
            text = text.replace(replacement, original)

    selected_entry = None
    remaining_entries = []

    for row in force_entries or []:
        if row.get("dependency") == dependency:
            selected_entry = row
        else:
            remaining_entries.append(row)

    if selected_entry is None:
        return text

    # org.springframework.boot:* (the platform itself) is pinned via the
    # Spring Boot Gradle plugin's own version declaration, not a force line —
    # write_gradle_file rewrites that line directly and never emits a force
    # for these, so the generic _remove_gradle_force fallback below would
    # find nothing to undo and silently no-op, leaving the bump in place even
    # though this candidate was supposed to be reverted. Regenerate the
    # plugin version from whatever boot-family force entries remain instead
    # (falling back to this candidate's own old_version when it was the last
    # one), mirroring how the managed_property branch below regenerates ext
    # properties from the remaining entries.
    if dependency.startswith("org.springframework.boot:") and is_spring_boot_managed_project(text):
        remaining_boot_entries = [
            row
            for row in remaining_entries
            if str(row.get("dependency", "")).startswith("org.springframework.boot:")
        ]
        if not remaining_boot_entries:
            remaining_boot_entries = [
                {
                    "dependency": dependency,
                    "new_version": selected_entry.get("old_version", ""),
                }
            ]
        text, _ = write_spring_boot_plugin_version(text, remaining_boot_entries)
        return text

    managed_property = spring_boot_managed_property(dependency)

    if (
        managed_property
        and is_spring_boot_managed_project(text)
    ):
        # Reconstruct every managed property from the force entries that remain
        # active in this rollback trial.
        managed_property_names = {
            spring_boot_managed_property(
                row.get("dependency", "")
            )
            for row in force_entries or []
        }
        managed_property_names.discard(None)

        for property_name in managed_property_names:
            text = re.sub(
                r"(?m)^\s*set\(\s*['\"]"
                + re.escape(property_name)
                + r"['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)\s*$\n?",
                "",
                text,
            )
            text = re.sub(
                r"(?m)^\s*ext\[\s*['\"]"
                + re.escape(property_name)
                + r"['\"]\s*\]\s*=\s*['\"][^'\"]+['\"]\s*$\n?",
                "",
                text,
            )

        text, _ = write_spring_boot_managed_properties(
            text,
            remaining_entries,
        )
        return text

    return _remove_gradle_force(
        text,
        dependency,
        selected_entry.get("new_version", ""),
    )


def _step_down_gradle_force(build_text: str, dependency: str, from_version: str, to_version: str) -> str:
    """Like _remove_gradle_force, but pins to `to_version` instead of dropping the force."""
    target = f"{dependency}:{from_version}"
    replacement = f"{dependency}:{to_version}"
    lines = []
    for line in build_text.splitlines():
        if "force " in line and target in line:
            lines.append(line.replace(target, replacement))
        else:
            lines.append(line)
    return "\n".join(lines) + ("\n" if build_text.endswith("\n") else "")


def _revert_gradle_package_to_version(
    current_text: str,
    changes: list[dict[str, str]] | None,
    force_entries: list[dict[str, str]] | None,
    dependency: str,
    target_version: str,
) -> str | None:
    """Pin `dependency` to `target_version` instead of fully reverting it.

    Used to try a still-non-vulnerable version between the originally chosen
    target and the pre-remediation original, before giving up on this
    package's CVE fix entirely. Returns None when this candidate isn't safe
    to step (Spring Boot BOM-managed properties apply to every family member
    at once, so partially stepping one down isn't representable this way).
    """
    from output.gradle import is_spring_boot_managed_project, spring_boot_managed_property

    for row in changes or []:
        if row.get("dependency") != dependency:
            continue
        original = row.get("original", "")
        replacement = row.get("replacement", "")
        old_version = row.get("old_version", "")
        if not (original and replacement):
            return None
        stepped = original.replace(old_version, target_version, 1)
        return current_text.replace(replacement, stepped)

    if dependency.startswith("org.springframework.boot:") and is_spring_boot_managed_project(current_text):
        # Same reasoning as the managed_property check below: the platform
        # version applies to every org.springframework.boot:* artifact at
        # once via the plugin declaration, and there's no force line for
        # _step_down_gradle_force to find (write_gradle_file rewrites the
        # plugin version directly) — partial stepping isn't representable.
        return None

    for row in force_entries or []:
        if row.get("dependency") != dependency:
            continue
        if spring_boot_managed_property(dependency) and is_spring_boot_managed_project(current_text):
            return None
        return _step_down_gradle_force(
            current_text,
            dependency,
            row.get("new_version", ""),
            target_version,
        )

    return None


def _make_gradle_step_down_fn(
    base_url: str | None,
    auth: tuple[str, str] | None,
    xray_host: str | None,
    timeout: int,
    repo_urls: list[str] | None,
) -> Callable[[dict, str], str | None] | None:
    """Build a step_down_fn that finds the next-lower non-vulnerable, accessible
    version for a candidate, reusing the same accessibility+CVE search already
    trusted for the blocked-version fallback path. Returns None (no ladder) when
    there's no base_url to query — the CVE filter can't be trusted without it.
    """
    if not base_url:
        return None

    def _step_down(candidate: dict, last_version: str) -> str | None:
        dependency = candidate.get("package", "")
        if ":" not in dependency:
            return None
        group, artifact = dependency.split(":", 1)

        start = MavenVersion.parse(last_version)
        old = MavenVersion.parse(candidate.get("old", ""))
        if start is None or old is None or old >= start:
            return None

        from parsers.gradle import find_accessible_version, get_available_versions

        available, _ = get_available_versions(group, artifact, base_url, auth, timeout)
        if not available:
            return None

        candidates_below = [v for v in available if old < v < start]
        if not candidates_below:
            return None

        return find_accessible_version(
            group, artifact, start, candidates_below, base_url, auth, timeout,
            xray_host=xray_host, repo_urls=repo_urls,
        )

    return _step_down


def _gradle_candidates(
    changes: list[dict[str, str]] | None,
    force_entries: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for row in changes or []:
        package = row.get("dependency", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "gradle",
                "old": row.get("old_version", ""),
                "new": row.get("new_version", ""),
            }
        )
        seen.add(package)
    for row in force_entries or []:
        package = row.get("dependency", "")
        if not package or package in seen:
            continue
        rows.append(
            {
                "package": package,
                "change_type": "gradle-force",
                "old": row.get("old_version", ""),
                "new": row.get("new_version", ""),
            }
        )
        seen.add(package)
    return rows


def _proactive_check_and_fix(
    build_file: str,
    gradle_cmd: str,
    timeout: int,
    log_dir: str | None,
    auth: tuple[str, str] | None,
    xray_host: str | None,
    base_url: str | None,
    repo_urls: list[str] | None = None,
) -> None:
    """Resolve the post-change dependency tree and proactively force any Xray-blocked
    transitives before running the full build.

    `gradlew dependencies` is far cheaper than a full build, so doing this once here
    replaces the multi-round reactive ext-fix loop that each require a complete rebuild.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import as_completed as _as_completed

    from output.gradle import write_dependency_substitutions, write_resolution_forces
    from parsers.gradle import (
        find_accessible_version,
        get_available_versions,
        parse_gradle_deps,
        parse_gradle_repositories,
    )
    from parsers.gradle_tree import (
        parse_gradle_dep_tree,
        run_gradle_dependencies_with_fallback,
    )
    from registry.maven import version_accessible

    if not base_url:
        return

    project_dir = os.path.dirname(os.path.abspath(build_file))
    build_path = Path(build_file)

    # Prefer the Gradle-evaluated repo URLs threaded in from resolve_tree — a
    # regex parse of the build file returns unresolved property references
    # like "${ARTIFACTORY_SOURCE}" verbatim, which then breaks every
    # accessibility probe run against them. Falls back to the regex parse
    # when the caller didn't have a resolved list available.
    build_text = build_path.read_text(encoding="utf-8")
    build_repo_urls = repo_urls or (parse_gradle_repositories(build_text) or None)

    _dbg(log_dir, "proactive check: resolving post-change dependency tree...")

    # `gradle dependencies` is the same operation resolve_tree runs, which floors
    # its timeout at 180s (managers/gradle.py) because large projects routinely
    # exceed the 30s default gradle_timeout on this step alone. Without the same
    # floor here, this check timed out on every single batch run for some repos
    # (e.g. ins-cp-mgmt-admin-api's dependency tree never resolved inside 30s in
    # any of its runs) — pure wasted time with zero benefit.
    tree_timeout = max(timeout, 180)

    # A package blocked severely enough to break tree resolution itself (not just
    # the final build) used to make this whole proactive check bail out silently
    # — there was no resolved tree to scan for accessibility, so the pipeline fell
    # through to the real, expensive build, which failed for the identical reason
    # and only got fixed reactively (_try_fix_external_gradle_blockers) after that
    # failure. run_gradle_dependencies_with_fallback already implements exactly
    # the "detect blocked from a failed scan, force an accessible replacement,
    # retry the scan" loop — resolve_tree (managers/gradle.py) already uses it for
    # the pre-change tree. Reusing it here closes the gap: scan first, then build.
    deps = parse_gradle_deps(build_text)
    stdout = None
    scan_bumped: dict[str, str] = {}
    for config in ("runtimeClasspath", "compileClasspath"):
        out, err, cfg_bumped = run_gradle_dependencies_with_fallback(
            project_dir=project_dir,
            build_file=build_file,
            deps=deps,
            available_by_key={},
            base_url=base_url,
            auth=auth,
            gradle_cmd=gradle_cmd,
            timeout=tree_timeout,
            configuration=config,
        )
        if cfg_bumped:
            scan_bumped.update(cfg_bumped)
        if out:
            stdout = out
            break
        _dbg(log_dir, f"proactive check: {config} failed — {(err or '')[:200]}")
        # The debug log only keeps a 200-char preview above; the parser that
        # decides whether this failure is fixable (_parse_blocked_packages,
        # inside run_gradle_dependencies_with_fallback) needs the full text,
        # and whether it actually matched real 403 output here has not yet
        # been confirmed against a real batch run — keep the untruncated
        # failure so that can be checked directly next time.
        if log_dir:
            with contextlib.suppress(Exception):
                Path(log_dir, f"gradle-dependency-tree-scan-failure-{config}.txt").write_text(
                    err or "", encoding="utf-8",
                )

    if scan_bumped:
        old_version_by_key = {f"{dep.group}:{dep.artifact}": dep.version for dep in deps}
        scan_force_entries = [
            {
                "dependency": key,
                "old_version": old_version_by_key.get(key, ""),
                "new_version": forced_version,
                "minimum_required": forced_version,
            }
            for key, forced_version in scan_bumped.items()
        ]
        build_text = write_resolution_forces(build_text, scan_force_entries)
        build_text = write_dependency_substitutions(build_text, scan_force_entries)
        build_path.write_text(build_text, encoding="utf-8")
        _write_external_auto_fixes(
            log_dir,
            [
                {
                    "dependency": row["dependency"],
                    "blocked_version": row["old_version"],
                    "forced_version": row["new_version"],
                    "status": "proactive_scan_force",
                    "reason": (
                        "forced to make the post-change dependency tree "
                        "resolvable before the real build"
                    ),
                }
                for row in scan_force_entries
            ],
        )
        _dbg(
            log_dir,
            f"proactive check: forced {len(scan_force_entries)} artifact(s) just to "
            "make the dependency tree resolve: "
            + ", ".join(f"{row['dependency']}:{row['new_version']}" for row in scan_force_entries),
        )

    if not stdout:
        _dbg(
            log_dir,
            "proactive check: could not resolve dependency tree even after "
            "forcing accessible replacements, skipping",
        )
        return

    installed, _ = parse_gradle_dep_tree(stdout)
    if not installed:
        return

    if log_dir:
        with contextlib.suppress(Exception):
            Path(log_dir, "gradle-dependency-tree-after.txt").write_text(
                stdout,
                encoding="utf-8",
            )

    _dbg(log_dir, f"proactive check: {len(installed)} resolved artifacts — checking accessibility...")

    def _check(item: tuple) -> tuple:
        key, mv = item
        group, artifact = key.split(":", 1)
        version = str(mv)
        check_urls = list(dict.fromkeys((build_repo_urls or []) + ([base_url] if base_url else [])))
        ok = any(version_accessible(group, artifact, version, url, auth, timeout) for url in check_urls)
        return key, group, artifact, version, ok

    blocked_items: list[tuple[str, str, str, str]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_check, item): item for item in installed.items()}
        for future in _as_completed(futures):
            try:
                key, group, artifact, version, accessible = future.result()
                if not accessible:
                    blocked_items.append((key, group, artifact, version))
            except Exception:
                pass

    if not blocked_items:
        _dbg(log_dir, "proactive check: all artifacts accessible — no pre-flight forces needed")
        return

    # A repository/authentication/transport failure can make every probe return
    # inaccessible at once. Treating that as hundreds of independent Xray blocks
    # causes bogus replacement searches, manual-update records, and rollbacks.
    # Real policy blocks normally affect only a subset of the resolved graph, so
    # let the normal Gradle build provide the authoritative failure in this case.
    if len(installed) >= 10 and len(blocked_items) == len(installed):
        _dbg(
            log_dir,
            "proactive check: all resolved artifacts were reported inaccessible; "
            "assuming repository/authentication/transport failure and skipping "
            "pre-flight forces",
        )
        return

    _dbg(log_dir, f"proactive check: {len(blocked_items)} blocked artifact(s) — finding replacements...")

    text = build_text
    force_entries: list[dict[str, str]] = []
    auto_rows: list[dict[str, str]] = []
    unresolved_rows: list[dict[str, str]] = []

    def _find_replacement(
        item: tuple[str, str, str, str],
    ) -> tuple[str, str, str, str, str | None, int, float, float]:
        key, group, artifact, version = item
        current = MavenVersion.parse(version)
        if current is None:
            return key, group, artifact, version, None, 0, 0.0, 0.0

        metadata_start = time.perf_counter()
        available, _ = get_available_versions(
            group,
            artifact,
            base_url,
            auth,
            timeout,
        )
        metadata_elapsed = time.perf_counter() - metadata_start
        if not available:
            return (
                key,
                group,
                artifact,
                version,
                None,
                0,
                metadata_elapsed,
                0.0,
            )

        search_start = time.perf_counter()
        forced = find_accessible_version(
            group,
            artifact,
            current,
            available,
            base_url,
            auth,
            timeout,
            xray_host=xray_host,
            repo_urls=build_repo_urls,
            log_dir=log_dir,
        )
        search_elapsed = time.perf_counter() - search_start

        return (
            key,
            group,
            artifact,
            version,
            forced,
            len(available),
            metadata_elapsed,
            search_elapsed,
        )

    # Metadata retrieval and replacement searches are independent across blocked
    # artifacts. Run those network-bound operations concurrently, while consuming
    # results in input order so generated Gradle changes and reports stay stable.
    lookup_workers = min(16, len(blocked_items))
    with ThreadPoolExecutor(max_workers=lookup_workers) as pool:
        replacement_results = pool.map(_find_replacement, blocked_items)

        for result in replacement_results:
            (
                key,
                group,
                artifact,
                version,
                forced,
                available_count,
                metadata_elapsed,
                search_elapsed,
            ) = result

            if not available_count:
                reason = (
                    "unparseable version"
                    if metadata_elapsed == 0.0
                    else "no versions available"
                )
                _dbg(
                    log_dir,
                    f"proactive check: {key}:{version} — "
                    f"{reason}; manual review required",
                )
                unresolved_rows.append(
                    {
                        "package": key,
                        "change_type": "external_blocker",
                        "old": version,
                        "new": "",
                        "status": "manual_update_required",
                        "reason": reason,
                    }
                )
                continue

            _dbg(
                log_dir,
                f"proactive check: metadata for {group}:{artifact} returned "
                f"{available_count} version(s) in {metadata_elapsed:.2f}s",
            )
            _dbg(
                log_dir,
                f"proactive check: replacement search for "
                f"{group}:{artifact}:{version} completed in "
                f"{search_elapsed:.2f}s -> {forced!r}",
            )

            if forced and forced != version:
                force_entries.append(
                    {
                        "dependency": key,
                        "old_version": version,
                        "new_version": forced,
                        "minimum_required": forced,
                    }
                )
                auto_rows.append(
                    {
                        "dependency": key,
                        "blocked_version": version,
                        "forced_version": forced,
                        "status": "proactive_force",
                        "reason": (
                            "blocked transitive detected in post-change "
                            "dependency tree"
                        ),
                    }
                )
            else:
                unresolved_rows.append(
                    {
                        "package": key,
                        "change_type": "external_blocker",
                        "old": version,
                        "new": "",
                        "status": "manual_update_required",
                        "reason": (
                            "no accessible non-vulnerable replacement found"
                        ),
                    }
                )

    if unresolved_rows and log_dir:
        _write_csv(
            Path(log_dir) / "build-validation-manual-updates.csv",
            unresolved_rows,
            [
                "package",
                "change_type",
                "old",
                "new",
                "status",
                "reason",
            ],
        )

    if not force_entries:
        _dbg(
            log_dir,
            "proactive check: no accessible replacement found for any "
            "blocked artifact — manual review required",
        )
        return unresolved_rows

    text = write_resolution_forces(text, force_entries)
    text = write_dependency_substitutions(text, force_entries)
    build_path.write_text(text, encoding="utf-8")
    _write_external_auto_fixes(log_dir, auto_rows)
    print(
        f"Proactive block check: forced {len(force_entries)} "
        "blocked transitive(s): "
        + ", ".join(
            f"{row['dependency']}:{row['forced_version']}"
            for row in auto_rows
        )
    )

    if unresolved_rows:
        _dbg(
            log_dir,
            f"proactive check: {len(unresolved_rows)} blocked artifact(s) "
            "still require manual review",
        )

    return unresolved_rows


def validate_gradle_project_or_rollback(
    build_file: str,
    original_build_text: str,
    gradle_cmd: str,
    timeout: int = 600,
    changes: list[dict[str, str]] | None = None,
    force_entries: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
    auth: tuple[str, str] | None = None,
    xray_host: str | None = None,
    base_url: str | None = None,
    enable_failure_isolation: bool = False,
    repo_urls: list[str] | None = None,
) -> None:
    from parsers.gradle import parse_gradle_repositories

    build_path = Path(build_file)

    # Pre-flight: resolve the post-change dependency tree and force any Xray-blocked
    # transitives before the first gradle build. gradlew dependencies is substantially
    # cheaper than gradle build and avoids multi-round reactive ext-fix loops.
    unresolved_blockers: list[dict[str, str]] = []
    if base_url:
        unresolved_blockers = _proactive_check_and_fix(
            build_file,
            gradle_cmd,
            timeout,
            log_dir,
            auth=auth,
            xray_host=xray_host,
            base_url=base_url,
            repo_urls=repo_urls,
        ) or []

    try:
        validate_gradle_project(
            build_file,
            gradle_cmd=gradle_cmd,
            timeout=timeout,
        )
    except BuildValidationError as first_error:
        failure_output = str(first_error)
        if "timed out after" in failure_output.lower() or _is_transient_daemon_crash(failure_output):
            retry_timeout = max(300, timeout * 3)
            _dbg(
                log_dir,
                "initial Gradle validation timed out or hit a transient daemon "
                f"crash; retrying the complete updated build with a {retry_timeout}s "
                "timeout before isolation",
            )
            try:
                validate_gradle_project(
                    build_file,
                    gradle_cmd=gradle_cmd,
                    timeout=retry_timeout,
                )
            except BuildValidationError as retry_error:
                failure_output = str(retry_error)
            else:
                if unresolved_blockers:
                    packages = ", ".join(
                        f"{row['package']}:{row['old']}"
                        for row in unresolved_blockers
                    )
                    _dbg(
                        log_dir,
                        "build passed on adaptive timeout retry, but blocked "
                        f"artifact(s) remain unresolved: {packages}",
                    )
                _clear_stale_validation_csvs(log_dir)
                return
    else:
        if unresolved_blockers:
            packages = ", ".join(
                f"{row['package']}:{row['old']}"
                for row in unresolved_blockers
            )
            _dbg(
                log_dir,
                "build passed, but blocked artifact(s) remain unresolved: "
                f"{packages}",
            )
        _clear_stale_validation_csvs(log_dir)
        return

    current_text = build_path.read_text(encoding="utf-8")
    external_blockers = _extract_gradle_blockers(failure_output)

    # Before blaming the updates, check whether this failure predates them.
    # Enterprise services routinely carry tests that cannot pass in the
    # remediation environment (Vault/Kafka/Mongo context loads, flaky suites);
    # without this check every trial fails, everything rolls back, and the
    # repo is reported Failed even though the updates broke nothing. Skipped
    # when the failure names download blockers — those come from the new
    # versions and the ext-fix path owns them.
    if not external_blockers and _extract_failing_tests(failure_output):
        baseline_failure = _gradle_baseline_failure(
            build_path, original_build_text, current_text, gradle_cmd, timeout,
        )
        if baseline_failure is not None and _is_preexisting_failure(
            baseline_failure, failure_output,
        ):
            _record_preexisting_failure(log_dir, baseline_failure)
            _clear_stale_validation_csvs(log_dir)
            print(
                "Build failure matches the pre-remediation baseline "
                "(same failing task and tests); keeping dependency updates."
            )
            return

    # Shared across the initial ext-fix call and all inline calls — prevents re-evaluating
    # the same blocked transitives at every greedy accumulation step.
    _ext_fix_handled: set[tuple[str, str, str]] = set()

    ext_fix_result = _try_fix_external_gradle_blockers(
        build_file, current_text, failure_output, gradle_cmd, timeout, log_dir,
        auth=auth, xray_host=xray_host, base_url=base_url,
        changes=changes, handled=_ext_fix_handled, repo_urls=repo_urls,
    ) if external_blockers else False
    if ext_fix_result is True:
        _clear_stale_validation_csvs(log_dir)
        return
    if isinstance(ext_fix_result, str):
        failure_output = ext_fix_result
        current_text = build_path.read_text(encoding="utf-8")

    def _inline_ext_fix(fail_str: str) -> bool:
        result = _try_fix_external_gradle_blockers(
            build_file, build_path.read_text(encoding="utf-8"), fail_str,
            gradle_cmd, timeout, log_dir,
            auth=auth, xray_host=xray_host, base_url=base_url,
            changes=None, handled=_ext_fix_handled, repo_urls=repo_urls,
        )
        return result is True

    # Prefer the Gradle-evaluated repo URLs threaded in from resolve_tree —
    # a regex parse of the build file returns unresolved property references
    # like "${ARTIFACTORY_SOURCE}" verbatim, which then breaks every
    # accessibility probe run against them. Falls back to the regex parse
    # when the caller didn't have a resolved list available (e.g. Phase 2
    # replay, whose cached result strips the GradleTree object).
    build_repo_urls = repo_urls if repo_urls else parse_gradle_repositories(current_text)

    validate_or_rollback(
        build_file,
        original_build_text,
        current_text,
        failure_output,
        _gradle_candidates(changes, force_entries),
        # A lighter task target during the search — compile + test, skipping
        # packaging/coverage tasks that don't bear on whether this candidate
        # fixes the failure. confirm_fn re-validates with the full "build"
        # before any trial is accepted, so this can't produce a false-positive
        # success just because a probe took a cheaper path than production.
        build_fn=lambda: validate_gradle_project(
            build_file, gradle_cmd=gradle_cmd, timeout=timeout, tasks="test",
        ),
        revert_fn=lambda text, c: _revert_gradle_package(text, changes, force_entries, c["package"]),
        log_dir=log_dir,
        ecosystem="gradle",
        pre_check_fn=_make_gradle_pre_check_fn(
            build_file,
            build_repo_urls,
            base_url,
            auth,
            timeout,
            baseline_text=original_build_text,
        ),
        ext_fix_fn=_inline_ext_fix,
        skip_implicate_check=isinstance(ext_fix_result, str),
        enable_failure_isolation=enable_failure_isolation,
        step_down_fn=_make_gradle_step_down_fn(base_url, auth, xray_host, timeout, build_repo_urls),
        revert_to_version_fn=lambda text, c, target: _revert_gradle_package_to_version(
            text, changes, force_entries, c["package"], target,
        ),
        confirm_fn=lambda: validate_gradle_project(
            build_file, gradle_cmd=gradle_cmd, timeout=timeout,
        ),
    )


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

def _python_candidates(changes: list[dict[str, str]] | None) -> list[dict[str, str]]:
    return [
        {
            "package": row["package"],
            "change_type": "python",
            "old": row["current_version"],
            "new": row["new_version"],
            "line_index": row["line_index"],
        }
        for row in (changes or [])
    ]


def validate_python_project(
    dep_file: str,
    python_cmd: str = "python",
    timeout: int = 600,
    file_type: str = "requirements",
) -> None:
    """Validate an updated Python project by running pip install."""
    project_dir = os.path.dirname(os.path.abspath(dep_file))
    if file_type == "requirements":
        cmd = [python_cmd, "-m", "pip", "install", "-r", dep_file]
        label = "pip install validation"
    else:
        cmd = [python_cmd, "-m", "pip", "install", "-e", "."]
        label = "pip install (pyproject) validation"
    _run_build_command(cmd, project_dir, timeout, label)


def validate_python_project_or_rollback(
    dep_file: str,
    original_text: str,
    python_cmd: str = "python",
    timeout: int = 600,
    changes: list[dict[str, str]] | None = None,
    log_dir: str | None = None,
    file_type: str = "requirements",
    enable_failure_isolation: bool = False,
) -> None:
    try:
        validate_python_project(dep_file, python_cmd=python_cmd, timeout=timeout, file_type=file_type)
        _clear_stale_validation_csvs(log_dir)
        return
    except BuildValidationError as first_error:
        failure_output = str(first_error)

    current_text = Path(dep_file).read_text(encoding="utf-8")

    validate_or_rollback(
        dep_file,
        original_text,
        current_text,
        failure_output,
        _python_candidates(changes),
        build_fn=lambda: validate_python_project(dep_file, python_cmd=python_cmd, timeout=timeout, file_type=file_type),
        revert_fn=lambda text, c: _revert_python_dep(text, c, file_type),
        log_dir=log_dir,
        ecosystem="python",
        enable_failure_isolation=enable_failure_isolation,
    )
