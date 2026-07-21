from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from shared.xray import filter_versions_without_cves


def probe_candidates_concurrently(
    candidates: list,
    is_accessible: Callable,
    max_workers: int = 8,
):
    """Return the first accessible candidate while probing speculatively.

    Candidate order defines preference. Once candidate N succeeds, pending probes
    after N are cancelled because they cannot beat it. Probes before N are allowed
    to finish because an earlier successful candidate must still win.

    Ecosystem-agnostic: `is_accessible` may run an HTTP probe, a subprocess probe,
    or anything else — this function only orders and cancels the futures. Callers
    cannot safely terminate work already executing in a thread (an in-flight HTTP
    request or subprocess). Cancellation therefore only stops pending work;
    already-running probes finish before the executor shuts down.
    """
    if not candidates:
        return None

    worker_count = max(1, min(max_workers, len(candidates)))
    executor = ThreadPoolExecutor(max_workers=worker_count)
    futures: dict[Future, int] = {}
    completed: dict[int, bool] = {}
    best_success: int | None = None

    try:
        for index, candidate in enumerate(candidates):
            futures[executor.submit(is_accessible, candidate)] = index

        pending = set(futures)
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)

            for future in done:
                index = futures[future]
                try:
                    accessible = bool(future.result())
                except Exception:
                    accessible = False

                completed[index] = accessible
                if accessible and (
                    best_success is None or index < best_success
                ):
                    best_success = index

                    # Later candidates are less preferred and cannot change the
                    # result. Cancel them if they have not started yet.
                    for other in list(pending):
                        if futures[other] > best_success and other.cancel():
                            pending.remove(other)

            if best_success is not None:
                earlier_indices = range(best_success)
                if all(index in completed for index in earlier_indices):
                    return candidates[best_success]

        if best_success is not None:
            return candidates[best_success]
        return None
    finally:
        # Do not wait for less-preferred probes that were already running.
        executor.shutdown(wait=False, cancel_futures=True)


def find_safe_version(
    forward_candidates: list,
    backward_candidates: list,
    is_accessible: Callable,
    ecosystem: str,
    package: str,
    xray_host: str | None = None,
    xray_auth: tuple | None = None,
    timeout: int = 30,
) -> tuple:
    """Return the first accessible, non-CVE version; forward candidates preferred.

    Both lists are filtered through Xray CVE lookup first. Surviving candidates
    within each direction are then probed concurrently via
    `probe_candidates_concurrently` (order-preserving: an earlier candidate that
    is slower to respond still wins over a faster later one) -- backward
    candidates are only probed if every forward candidate is inaccessible.

    Returns (version, diagnostic_str). diagnostic_str is empty on success.
    """
    forward_candidates, forward_cves, forward_xray_error = filter_versions_without_cves(
        ecosystem, package, forward_candidates,
        xray_host=xray_host, auth=xray_auth, timeout=timeout,
    )

    result = probe_candidates_concurrently(forward_candidates, is_accessible)

    # Every package used to pay for the backward Xray CVE lookup up front,
    # even though the accessibility probe below it was already correctly
    # lazy ("do not send backward probes unless every forward candidate
    # failed") -- a full extra sequential Xray round-trip (up to `timeout`)
    # on every package, whether or not backward was ever needed. The common
    # case (forward succeeds) is most packages, so this was pure unconditional
    # latency. Only pay for it when forward actually comes up empty.
    backward_cves: list = []
    backward_xray_error = ""
    if result is None:
        backward_candidates, backward_cves, backward_xray_error = filter_versions_without_cves(
            ecosystem, package, backward_candidates,
            xray_host=xray_host, auth=xray_auth, timeout=timeout,
        )
        result = probe_candidates_concurrently(backward_candidates, is_accessible)

    if result is not None:
        return result, ""

    xray_note = (
        f"; Xray lookup warning: {forward_xray_error or backward_xray_error}"
        if (forward_xray_error or backward_xray_error)
        else ""
    )
    cve_note = (
        f"; CVE-filtered candidates: {len(forward_cves) + len(backward_cves)}"
        if (forward_cves or backward_cves)
        else ""
    )
    return None, (
        f"all {len(forward_candidates)} forward and {len(backward_candidates)} backward "
        f"candidates are inaccessible{xray_note}{cve_note}"
    )
