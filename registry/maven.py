from __future__ import annotations

import os
import threading
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from unittest.mock import Mock

from shared.cache import cache_by_requests_transport
from shared.maven_version import MavenVersion

_thread_local = threading.local()
_limit_lock = threading.Lock()
_limit_value: int | None = None
_limit_semaphore: threading.BoundedSemaphore | None = None


def _global_artifactory_limit() -> int:
    """Return the process-wide Artifactory request limit.

    apply_updates already runs up to `workers` (default 8) keys concurrently,
    and each key's accessibility search (find_accessible_version ->
    probe_candidates_concurrently) fans out up to 8 more candidate probes of
    its own -- a cluster of related artifacts reported together by JFrog
    (e.g. 8 io.netty:* packages flagged in one audit) can want up to 64
    concurrent Artifactory requests at once. The old default of 8 forced all
    of that through a single shared slot, serializing most of it and turning
    a large-family cluster into a multi-minute stall even though no single
    request was slow. 24 gives substantially more real parallelism while
    still bounding total load on Artifactory well below the 64-wide peak.
    """
    raw = os.environ.get("PACKAGE_UPDATE_ARTIFACTORY_MAX_CONCURRENCY", "24")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 24


def _global_artifactory_semaphore() -> threading.BoundedSemaphore:
    global _limit_value, _limit_semaphore

    limit = _global_artifactory_limit()
    with _limit_lock:
        if _limit_semaphore is None or _limit_value != limit:
            _limit_value = limit
            _limit_semaphore = threading.BoundedSemaphore(limit)
        return _limit_semaphore


@contextmanager
def _artifactory_slot():
    semaphore = _global_artifactory_semaphore()
    semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()


def _build_session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry = Retry(
        total=3,
        connect=3,
        read=2,
        status=3,
        backoff_factor=0.25,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=16,
        pool_maxsize=16,
        pool_block=True,
    )
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "package-update-tool/1.0"})
    return session


def _session():
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = _build_session()
        _thread_local.session = session
    return session


def _get(url: str, **kwargs):
    import requests

    # Preserve compatibility with tests and callers that monkeypatch requests.get.
    transport = requests.get if isinstance(requests.get, Mock) else _session().get
    with _artifactory_slot():
        return transport(url, **kwargs)


def _head(url: str, **kwargs):
    import requests

    # Preserve compatibility with tests and callers that monkeypatch requests.head.
    transport = requests.head if isinstance(requests.head, Mock) else _session().head
    with _artifactory_slot():
        return transport(url, **kwargs)


@cache_by_requests_transport
def get_available_versions(
    group: str,
    artifact: str,
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
) -> tuple[list[MavenVersion], str]:
    group_path = group.replace(".", "/")
    url = f"{base_url}/{group_path}/{artifact}/maven-metadata.xml"

    try:
        response = _get(url, auth=auth, timeout=timeout)
    except Exception as exc:
        return [], f"request failed: {exc}"

    if response.status_code != 200:
        return [], f"HTTP {response.status_code} for {url}"

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        return [], f"XML parse error: {exc}"

    versions = []
    for node in root.findall(".//version"):
        raw = (node.text or "").strip()
        version = MavenVersion.parse(raw)
        if version:
            versions.append(version)

    return sorted(versions), ""


@cache_by_requests_transport
def version_accessible(
    group: str,
    artifact: str,
    version: str,
    base_url: str,
    auth: tuple[str, str] | None,
    timeout: int,
) -> bool:
    group_path = group.replace(".", "/")
    base = (
        f"{base_url}/{group_path}/{artifact}/{version}/"
        f"{artifact}-{version}"
    )

    # Gradle commonly requests module metadata before the primary artifact.
    # A policy may block the module independently, so an explicit 403 is final.
    module_url = f"{base}.module"
    try:
        response = _head(
            module_url,
            auth=auth,
            allow_redirects=True,
            timeout=timeout,
        )
        if response.status_code == 403:
            return False
    except Exception:
        pass

    # Normal Maven libraries must have an accessible JAR. A 403 means Xray or
    # repository policy rejected the actual binary and must not be bypassed just
    # because its POM remains readable.
    jar_url = f"{base}.jar"
    try:
        response = _head(
            jar_url,
            auth=auth,
            allow_redirects=True,
            timeout=timeout,
        )
        if response.status_code == 200:
            return True
        if response.status_code == 403:
            return False
    except Exception:
        pass

    # BOMs and parent artifacts are intentionally POM-only and therefore have no
    # JAR. When the JAR is absent, inspect the POM and accept the version only if
    # Maven explicitly declares packaging=pom. Maven's default packaging is jar,
    # so a missing packaging element must not be treated as a POM-only artifact.
    pom_url = f"{base}.pom"
    try:
        response = _get(
            pom_url,
            auth=auth,
            allow_redirects=True,
            timeout=timeout,
        )
        if response.status_code != 200:
            return False

        root = ET.fromstring(response.text)
        packaging = root.find("./{*}packaging")
        return (
            packaging is not None
            and (packaging.text or "").strip().lower() == "pom"
        )
    except (ET.ParseError, Exception):
        return False
