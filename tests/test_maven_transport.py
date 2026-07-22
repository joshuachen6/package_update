from __future__ import annotations

import threading


def test_maven_http_uses_thread_local_sessions(monkeypatch):
    from registry import maven

    monkeypatch.setattr(maven, "_thread_local", threading.local())
    created = []

    class DummySession:
        pass

    def fake_build_session():
        session = DummySession()
        created.append(session)
        return session

    monkeypatch.setattr(maven, "_build_session", fake_build_session)

    main_session_1 = maven._session()
    main_session_2 = maven._session()
    assert main_session_1 is main_session_2
    worker_sessions = []

    def get_worker_session():
        worker_sessions.append(maven._session())

    thread = threading.Thread(target=get_worker_session)
    thread.start()
    thread.join()

    assert worker_sessions[0] is not main_session_1
    assert len(created) == 2


def test_artifactory_global_limit_default_and_invalid_env(monkeypatch):
    from registry import maven

    monkeypatch.delenv("PACKAGE_UPDATE_ARTIFACTORY_MAX_CONCURRENCY", raising=False)
    assert maven._global_artifactory_limit() == 24
    monkeypatch.setenv("PACKAGE_UPDATE_ARTIFACTORY_MAX_CONCURRENCY", "3")
    assert maven._global_artifactory_limit() == 3

    monkeypatch.setenv("PACKAGE_UPDATE_ARTIFACTORY_MAX_CONCURRENCY", "bad")
    assert maven._global_artifactory_limit() == 24

    monkeypatch.setenv("PACKAGE_UPDATE_ARTIFACTORY_MAX_CONCURRENCY", "0")
    assert maven._global_artifactory_limit() == 1


def test_maven_bom_is_accessible_when_pom_packaging_is_pom(monkeypatch):
    from registry import maven

    class Response:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

        def close(self):
            pass

    def fake_head(url, **kwargs):
        if url.endswith(".module"):
            return Response(404)
        raise AssertionError(url)

    def fake_get(url, **kwargs):
        if url.endswith(".jar"):
            return Response(404)
        assert url.endswith(".pom")
        return Response(
            200,
            (
                '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                "<modelVersion>4.0.0</modelVersion>"
                "<packaging>pom</packaging>"
                "</project>"
            ),
        )

    monkeypatch.setattr(maven, "_head", fake_head)
    monkeypatch.setattr(maven, "_get", fake_get)
    maven.version_accessible.cache_clear()

    assert maven.version_accessible(
        "com.fasterxml.jackson",
        "jackson-bom",
        "2.21.2",
        "https://repo.example",
        None,
        30,
    )


def test_maven_does_not_accept_readable_pom_when_jar_is_blocked(
    monkeypatch,
):
    from registry import maven

    class Response:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

        def close(self):
            pass

    def fake_head(url, **kwargs):
        if url.endswith(".module"):
            return Response(404)
        raise AssertionError(url)

    def fake_get(url, **kwargs):
        if url.endswith(".jar"):
            return Response(403)
        raise AssertionError("POM must not bypass a blocked JAR")

    monkeypatch.setattr(maven, "_head", fake_head)
    monkeypatch.setattr(maven, "_get", fake_get)
    maven.version_accessible.cache_clear()

    assert not maven.version_accessible(
        "org.example",
        "regular-library",
        "1.2.3",
        "https://repo.example",
        None,
        30,
    )


def test_maven_jar_check_uses_get_not_head_so_download_policy_blocks_are_caught(
    monkeypatch,
):
    """Real-world bug: a HEAD request for jackson-databind's jar came back 200
    (accessible) on a real batch run, but the actual Gradle build then hit a
    403 downloading the same jar/version -- Xray's download-policy enforcement
    only triggers on the real retrieval, not a HEAD existence check. The probe
    must use the same request method (GET) Gradle's real resolution uses, or
    it silently selects/writes a version that's blocked in practice.
    """
    from registry import maven

    class Response:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text
            self.closed = False

        def close(self):
            self.closed = True

    def fake_head(url, **kwargs):
        if url.endswith(".module"):
            return Response(404)
        raise AssertionError("Only .module should ever be HEAD-checked")

    jar_response = Response(403)

    def fake_get(url, **kwargs):
        if url.endswith(".jar"):
            # A HEAD for this exact artifact would return 200 in the real
            # incident; the fix must not rely on HEAD at all for the jar.
            assert kwargs.get("stream") is True
            return jar_response
        raise AssertionError(url)

    monkeypatch.setattr(maven, "_head", fake_head)
    monkeypatch.setattr(maven, "_get", fake_get)
    maven.version_accessible.cache_clear()

    assert not maven.version_accessible(
        "com.fasterxml.jackson.core",
        "jackson-databind",
        "2.22.1",
        "https://repo.example",
        None,
        30,
    )
    assert jar_response.closed, "streamed GET response must be closed after status check"


def test_maven_missing_jar_requires_explicit_pom_packaging(monkeypatch):
    from registry import maven

    class Response:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

        def close(self):
            pass

    monkeypatch.setattr(
        maven,
        "_head",
        lambda url, **kwargs: Response(404),
    )

    def fake_get(url, **kwargs):
        if url.endswith(".jar"):
            return Response(404)
        return Response(
            200,
            "<project><modelVersion>4.0.0</modelVersion></project>",
        )

    monkeypatch.setattr(maven, "_get", fake_get)
    maven.version_accessible.cache_clear()

    assert not maven.version_accessible(
        "org.example",
        "missing-library",
        "1.2.3",
        "https://repo.example",
        None,
        30,
    )
