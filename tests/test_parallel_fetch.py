from __future__ import annotations

import threading
import time


def test_parallel_fetch_enforces_per_item_deadline(monkeypatch):
    from shared import parallel

    class SilentProgress:
        def __init__(self, *args, **kwargs):
            pass

        def update(self, step=1):
            pass

    monkeypatch.setattr(parallel, "ProgressBar", SilentProgress)

    release_slow_item = threading.Event()

    def fetch(item):
        if item == "slow":
            release_slow_item.wait(5)
            return item, [item], ""
        return item, [item], ""

    start = time.monotonic()
    results, errors = parallel.parallel_fetch(
        fetch,
        ["fast-1", "fast-2", "slow"],
        "Fetching Artifactory versions (2 workers)",
        workers=2,
        item_timeout=0.2,
    )
    elapsed = time.monotonic() - start
    release_slow_item.set()

    assert elapsed < 1.0
    assert results["fast-1"] == ["fast-1"]
    assert results["fast-2"] == ["fast-2"]
    assert results["slow"] == []
    assert errors == [("slow", "timed out after 0.2s")]


def test_parallel_fetch_can_wait_for_all_items_without_item_timeout(monkeypatch):
    from shared import parallel

    class SilentProgress:
        def __init__(self, *args, **kwargs):
            pass

        def update(self, step=1):
            pass

    monkeypatch.setattr(parallel, "ProgressBar", SilentProgress)

    def fetch(item):
        if item == "slow":
            time.sleep(0.05)
        return item, [item], ""

    results, errors = parallel.parallel_fetch(
        fetch,
        ["fast", "slow"],
        "Fetching Artifactory versions (2 workers)",
        workers=2,
        item_timeout=None,
    )

    assert results == {"fast": ["fast"], "slow": ["slow"]}
    assert errors == []
