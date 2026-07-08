import json

import shared.cve_lookup as cve


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_extract_advisory_id_prefers_ghsa_and_uppercases_cve():
    assert (
        cve.extract_advisory_id("Fix ghsa-abcd-1234-ef56 and CVE-2026-12345")
        == "ghsa-abcd-1234-ef56"
    )
    assert cve.extract_advisory_id("fix cve-2026-12345 now") == "CVE-2026-12345"
    assert cve.extract_advisory_id("no advisory here") is None


def test_lookup_osv_success_and_error(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["ua"] = req.headers["User-agent"]
        seen["timeout"] = timeout
        return DummyResponse({"id": "GHSA-abcd-1234-ef56"})

    monkeypatch.setattr(cve.urllib.request, "urlopen", fake_urlopen)

    assert cve.lookup_osv("GHSA-abcd-1234-ef56", timeout=3) == {"id": "GHSA-abcd-1234-ef56"}
    assert seen["url"].endswith("/GHSA-abcd-1234-ef56")
    assert seen["ua"] == "package-update-tool/1.0"
    assert seen["timeout"] == 3

    monkeypatch.setattr(
        cve.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("down")),
    )
    assert cve.lookup_osv("CVE-2026-12345") is None


def test_get_fixed_versions_filters_ecosystem_and_missing_names():
    data = {
        "affected": [
            {
                "package": {"ecosystem": "npm", "name": "lodash"},
                "ranges": [{"events": [{"introduced": "0"}, {"fixed": "4.17.21"}]}],
            },
            {
                "package": {"ecosystem": "npm", "name": "lodash"},
                "ranges": [{"events": [{"fixed": "4.17.20"}]}],
            },
            {
                "package": {"ecosystem": "Maven", "name": "org.example:lib"},
                "ranges": [{"events": [{"fixed": "1.2.3"}]}],
            },
            {
                "package": {"ecosystem": "npm", "name": ""},
                "ranges": [{"events": [{"fixed": "1.0.0"}]}],
            },
        ]
    }

    assert cve.get_fixed_versions(data, "npm") == {"lodash": ["4.17.21", "4.17.20"]}
    assert cve.get_fixed_versions(data, "maven") == {"org.example:lib": ["1.2.3"]}


def test_lookup_nvd_success_empty_and_error(monkeypatch):
    payload = {"vulnerabilities": [{"cve": {"id": "CVE-2026-12345"}}]}
    monkeypatch.setattr(cve.urllib.request, "urlopen", lambda req, timeout: DummyResponse(payload))
    assert cve._lookup_nvd("CVE-2026-12345", 2) == {"id": "CVE-2026-12345"}

    monkeypatch.setattr(
        cve.urllib.request,
        "urlopen",
        lambda req, timeout: DummyResponse({"vulnerabilities": []}),
    )
    assert cve._lookup_nvd("CVE-2026-12345", 2) is None

    monkeypatch.setattr(
        cve.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("bad")),
    )
    assert cve._lookup_nvd("CVE-2026-12345", 2) is None


def test_get_fixed_versions_from_nvd_filters_sources_ecosystems_and_versions():
    nvd = {
        "affected": [
            {
                "source": "security-advisories@github.com",
                "affectedData": [
                    {
                        "product": "lodash",
                        "versions": [
                            {"status": "affected", "version": "< 4.17.21"},
                            {"status": "affected", "version": ">= 4.0.0, < 4.17.20"},
                            {"status": "unaffected", "version": "< 3.0.0"},
                        ],
                    },
                    {
                        "product": "org.example:lib",
                        "versions": [{"status": "affected", "version": "< 1.2.3"}],
                    },
                    {
                        "product": "",
                        "versions": [{"status": "affected", "version": "< 9.9.9"}],
                    },
                ],
            },
            {
                "source": "redhat",
                "affectedData": [
                    {
                        "product": "ignored",
                        "versions": [{"status": "affected", "version": "< 1.0.0"}],
                    }
                ],
            },
        ]
    }

    assert cve._get_fixed_versions_from_nvd(nvd, "npm") == {"lodash": ["4.17.21", "4.17.20"]}
    assert cve._get_fixed_versions_from_nvd(nvd, "maven") == {"org.example:lib": ["1.2.3"]}


def test_resolve_advisory_osv_direct(monkeypatch):
    monkeypatch.setattr(
        cve,
        "lookup_osv",
        lambda advisory_id, timeout: {
            "affected": [
                {
                    "package": {"ecosystem": "npm", "name": "pkg"},
                    "ranges": [{"events": [{"fixed": "1.0.1"}]}],
                }
            ]
        },
    )

    assert cve.resolve_advisory("GHSA-abcd-1234-ef56", "npm") == {"pkg": ["1.0.1"]}


def test_resolve_advisory_chases_ghsa_alias(monkeypatch):
    calls = []

    def fake_lookup(advisory_id, timeout):
        calls.append(advisory_id)
        if advisory_id == "CVE-2026-12345":
            return {"aliases": ["CVE-OTHER", "GHSA-abcd-1234-ef56"], "affected": []}
        return {
            "affected": [
                {
                    "package": {"ecosystem": "npm", "name": "pkg"},
                    "ranges": [{"events": [{"fixed": "2.0.0"}]}],
                }
            ]
        }

    monkeypatch.setattr(cve, "lookup_osv", fake_lookup)

    assert cve.resolve_advisory("CVE-2026-12345", "npm") == {"pkg": ["2.0.0"]}
    assert calls == ["CVE-2026-12345", "GHSA-abcd-1234-ef56"]


def test_resolve_advisory_uses_nvd_for_cve_fallback(monkeypatch):
    monkeypatch.setattr(cve, "lookup_osv", lambda advisory_id, timeout: None)
    monkeypatch.setattr(
        cve,
        "_lookup_nvd",
        lambda advisory_id, timeout: {
            "affected": [
                {
                    "source": "security-advisories@github.com",
                    "affectedData": [
                        {
                            "product": "pkg",
                            "versions": [{"status": "affected", "version": "< 3.0.0"}],
                        }
                    ],
                }
            ]
        },
    )

    assert cve.resolve_advisory("CVE-2026-99999", "npm") == {"pkg": ["3.0.0"]}


def test_resolve_advisory_empty_when_no_data(monkeypatch):
    monkeypatch.setattr(
        cve, "lookup_osv", lambda advisory_id, timeout: {"aliases": [], "affected": []}
    )
    monkeypatch.setattr(cve, "_lookup_nvd", lambda advisory_id, timeout: None)

    assert cve.resolve_advisory("CVE-2026-0000", "npm") == {}
    assert cve.resolve_advisory("GHSA-abcd-1234-ef56", "npm") == {}


def test_prefetch_advisories_deduplicates_and_caches(monkeypatch, capsys):
    calls = []

    def fake_resolve(advisory_id, ecosystem, timeout):
        calls.append((advisory_id, ecosystem, timeout))
        if advisory_id.startswith("CVE"):
            return {"pkg": ["1.0.0"]}
        return {}

    monkeypatch.setattr(cve, "resolve_advisory", fake_resolve)

    rows = [
        (1, "CVE-2026-12345 first", "text"),
        (2, "cve-2026-12345 duplicate lower", "text"),
        (3, "GHSA-abcd-1234-ef56 second", "text"),
        (4, "nothing", "text"),
    ]

    result = cve.prefetch_advisories(rows, "npm", workers=4, timeout=6)
    assert result["CVE-2026-12345"] == {"pkg": ["1.0.0"]}
    assert result["GHSA-abcd-1234-ef56"] == {}
    assert sorted(calls) == [
        ("CVE-2026-12345", "npm", 6),
        ("GHSA-abcd-1234-ef56", "npm", 6),
    ]

    out = capsys.readouterr().out
    assert "OSV: CVE-2026-12345" in out
    assert "falling back to NLP" in out


def test_prefetch_advisories_returns_empty_without_ids(monkeypatch):
    monkeypatch.setattr(
        cve,
        "resolve_advisory",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not call")),
    )

    assert cve.prefetch_advisories([(1, "no id", "text")], "npm") == {}
