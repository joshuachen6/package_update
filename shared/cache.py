"""Small in-process cache decorators for external command/network lookups."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar
from unittest.mock import Mock

F = TypeVar("F", bound=Callable[..., Any])


def _cache_key(
    args: tuple[Any, ...], kwargs: dict[str, Any], transport_ids: tuple[int, ...]
) -> tuple[Any, ...]:
    """Build a cache key that changes when test monkeypatches replace transports."""
    return args, tuple(sorted(kwargs.items())), transport_ids


def cache_by_subprocess_run[F: Callable[..., Any]](func: F) -> F:
    """Cache calls while invalidating when subprocess.run is monkeypatched."""
    cache: dict[tuple[Any, ...], Any] = {}

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = _cache_key(args, kwargs, (id(subprocess.run),))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


def cache_by_requests_transport[F: Callable[..., Any]](func: F) -> F:
    """Cache requests-based calls while invalidating when requests is monkeypatched.

    Tests patch requests.get/head with Mock objects repeatedly. Mock object ids can
    be reused after patch contexts exit, so bypass caching for mocked transports to
    prevent stale mocked HTTP responses from leaking between tests.
    """
    cache: dict[tuple[Any, ...], Any] = {}

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        import requests

        if isinstance(requests.get, Mock) or isinstance(requests.head, Mock):
            return func(*args, **kwargs)

        key = _cache_key(args, kwargs, (id(requests.get), id(requests.head)))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]
