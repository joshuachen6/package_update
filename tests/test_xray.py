import base64
import json
import urllib.error

from shared.xray import ComponentVersion, filter_versions_without_cves, search_cves_by_components


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_search_cves_posts_component_ids_and_basic_auth(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=30):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data.decode("utf-8"))
        seen["auth"] = request.headers.get("Authorization")
        return FakeResponse(
            {
                "results": {
                    "npm://lodash:4.17.20": {
                        "vulnerabilities": [{"cve": "CVE-2021-1111"}]
                    }
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result, error = search_cves_by_components(
        [ComponentVersion("npm", "lodash", "4.17.20")],
        xray_host="jfrog.example.com",
        auth=("alice", "secret"),
        timeout=9,
    )

    expected_auth = "Basic " + base64.b64encode(b"alice:secret").decode("ascii")
    assert error == ""
    assert seen["url"] == "https://jfrog.example.com/xray/api/v1/component/searchCvesByComponents"
    assert seen["timeout"] == 9
    assert seen["body"] == {"components_id": ["npm://lodash:4.17.20"]}
    assert seen["auth"] == expected_auth
    assert result == {"npm://lodash:4.17.20": ["CVE-2021-1111"]}


def test_search_cves_supports_list_response_shape(monkeypatch):
    def fake_urlopen(request, timeout=30):
        return FakeResponse(
            {
                "results": [
                    {
                        "component_id": "gav://org.example:demo:1.0.0",
                        "cves": [{"cve": "CVE-2022-2222"}],
                    },
                    {
                        "componentId": "npm://safe:1.0.0",
                        "cves": [],
                    },
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result, error = search_cves_by_components(
        [
            ComponentVersion("maven", "org.example:demo", "1.0.0"),
            ComponentVersion("npm", "safe", "1.0.0"),
        ],
        xray_host="https://jfrog.example.com",
    )

    assert error == ""
    assert result == {"gav://org.example:demo:1.0.0": ["CVE-2022-2222"]}


def test_search_cves_supports_bearer_token(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=30):
        seen["auth"] = request.headers.get("Authorization")
        return FakeResponse({"results": {}})

    monkeypatch.setenv("JFROG_ACCESS_TOKEN", "token-123")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result, error = search_cves_by_components(
        [ComponentVersion("npm", "left-pad", "1.3.0")],
        xray_host="https://jfrog.example.com",
    )

    assert error == ""
    assert result == {}
    assert seen["auth"] == "Bearer token-123"


def test_search_cves_http_error_includes_body(monkeypatch):
    def fake_urlopen(request, timeout=30):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            {},
            None,
        )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result, error = search_cves_by_components(
        [ComponentVersion("npm", "left-pad", "1.3.0")],
        xray_host="https://jfrog.example.com",
    )

    assert result == {}
    assert "HTTP 401" in error


def test_filter_versions_without_cves_filters_only_vulnerable(monkeypatch):
    def fake_urlopen(request, timeout=30):
        return FakeResponse(
            {
                "results": {
                    "npm://demo:1.0.0": {"cves": [{"cve": "CVE-2020-0001"}]},
                }
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    safe, vulnerable, error = filter_versions_without_cves(
        "npm",
        "demo",
        ["1.0.0", "1.0.1"],
        xray_host="https://jfrog.example.com",
    )

    assert error == ""
    assert safe == ["1.0.1"]
    assert vulnerable == {"npm://demo:1.0.0": ["CVE-2020-0001"]}



def test_search_cves_strips_artifactory_path_before_calling_xray(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=30):
        seen["url"] = request.full_url
        return FakeResponse({"results": {}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result, error = search_cves_by_components(
        [ComponentVersion("npm", "lodash", "4.17.20")],
        xray_host="https://humana.jfrog.io/artifactory",
    )

    assert error == ""
    assert result == {}
    assert seen["url"] == "https://humana.jfrog.io/xray/api/v1/component/searchCvesByComponents"
