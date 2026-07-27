"""Ecosystem-agnostic build-validation engine.

Process management, output parsing, CSV logging, and the candidate-trial
isolation search shared by the Gradle/Node/Python validators in the sibling
`.gradle` / `.node` / `.python` modules. Nothing in this module refers to any
of them by name -- validate_or_rollback and _run_candidate_trials are driven
entirely through the build_fn/revert_fn/... callbacks each ecosystem module
supplies.
"""

from __future__ import annotations

import contextlib
import csv
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from itertools import combinations
from pathlib import Path


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
