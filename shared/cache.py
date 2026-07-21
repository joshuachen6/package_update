"""Small in-process cache decorators for external command/network lookups."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable
from functools import wraps
from typing import Any
from unittest.mock import Mock

_MISSING = object()


def _cache_key(
    args: tuple[Any, ...], kwargs: dict[str, Any], transport_ids: tuple[int, ...]
) -> tuple[Any, ...]:
    """Build a cache key that changes when test monkeypatches replace transports."""
    return args, tuple(sorted(kwargs.items())), transport_ids


def cache_by_subprocess_run[F: Callable[..., Any]](func: F) -> F:
    """Cache calls while invalidating when subprocess.run is monkeypatched."""
    cache: dict[tuple[Any, ...], Any] = {}
    lock = threading.Lock()

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = _cache_key(args, kwargs, (id(subprocess.run),))
        with lock:
            cached = cache.get(key, _MISSING)
        if cached is not _MISSING:
            return cached

        value = func(*args, **kwargs)
        with lock:
            cache.setdefault(key, value)
            return cache[key]

    wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


def cache_by_requests_transport[F: Callable[..., Any]](func: F) -> F:
    """Cache requests-based calls while invalidating when requests is monkeypatched.

    Thread-safe: only one thread fetches any given key; others wait for it.
    """
    cache: dict[tuple[Any, ...], Any] = {}
    lock = threading.Lock()
    in_flight: dict[tuple[Any, ...], threading.Event] = {}

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        import requests

        if isinstance(requests.get, Mock) or isinstance(requests.head, Mock):
            return func(*args, **kwargs)

        key = _cache_key(args, kwargs, (id(requests.get), id(requests.head)))

        with lock:
            if key in cache:
                return cache[key]
            event = in_flight.get(key)
            if event is None:
                event = threading.Event()
                in_flight[key] = event
                owner = True
            else:
                owner = False

        if owner:
            try:
                value = func(*args, **kwargs)
                with lock:
                    cache[key] = value
                    return value
            finally:
                with lock:
                    in_flight.pop(key, None)
                event.set()

        event.wait()
        with lock:
            return cache[key]

    wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
