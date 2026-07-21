from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from shared.utils import ProgressBar


def parallel_fetch(
    fn: Callable,
    items: list,
    label: str,
    workers: int,
    item_timeout: float | None = None,
) -> tuple[dict, list[tuple]]:
    """Run network fetches concurrently.

    ``fn(item)`` returns ``(key, value, error_string)``.

    When item_timeout is supplied, each item receives a deadline measured from
    submission. Pending work is cancelled when its deadline expires. Python
    cannot terminate a thread already inside a blocking network operation, so
    timed-out running work is abandoned and allowed to finish in the background.
    """
    results: dict = {}
    errors: list[tuple] = []
    progress = ProgressBar(len(items), label, enabled=bool(items))

    if not items:
        return results, errors

    executor = ThreadPoolExecutor(max_workers=max(1, workers))
    submitted_at = time.monotonic()
    futures = {executor.submit(fn, item): item for item in items}
    deadlines = {
        future: (
            submitted_at + item_timeout
            if item_timeout is not None
            else None
        )
        for future in futures
    }
    pending = set(futures)

    try:
        while pending:
            if item_timeout is None:
                wait_timeout = None
            else:
                now = time.monotonic()
                nearest = min(deadlines[future] for future in pending)
                wait_timeout = max(0.0, nearest - now)

            done, still_pending = wait(
                pending,
                timeout=wait_timeout,
                return_when=FIRST_COMPLETED,
            )
            pending = set(still_pending)

            for future in done:
                item = futures[future]
                try:
                    key, value, error = future.result()
                except Exception as exc:
                    key, value, error = item, [], str(exc)

                results[key] = value
                if error:
                    errors.append((key, error))
                progress.update()

            if item_timeout is None:
                continue

            now = time.monotonic()
            expired = [
                future
                for future in pending
                if deadlines[future] is not None
                and now >= deadlines[future]
            ]
            for future in expired:
                pending.remove(future)
                future.cancel()
                item = futures[future]
                results[item] = []
                errors.append(
                    (item, f"timed out after {item_timeout:g}s")
                )
                progress.update()
    finally:
        executor.shutdown(
            wait=item_timeout is None,
            cancel_futures=item_timeout is not None,
        )

    return results, errors
