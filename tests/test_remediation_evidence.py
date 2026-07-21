from __future__ import annotations

import json

from shared.remediation_evidence import (
    write_remediation_evidence,
)


def test_writes_remediation_evidence_with_scan_diff(tmp_path):
    results = {
        "cfg": {
            "log_dir": str(tmp_path),
            "enable_failure_isolation": True,
        },
        "verification": {
            "outcome": "Partial",
            "classification": "Partial - CVEs remain",
            "security_status": "still_vulnerable",
            "test_status": "passed",
            "original_cves": ["CVE-1", "CVE-2"],
            "remaining_original_cves": ["CVE-2"],
            "tests": {"status": "passed"},
        },
        "jfrog_result": {
            "vulnerability_count": 2,
            "vulnerable_components": [
                {
                    "component_id": "gav://g:a:1",
                    "ecosystem": "maven",
                    "package": "g:a",
                    "version": "1",
                    "cves": ["CVE-1", "CVE-2"],
                }
            ],
        },
        "jfrog_result_after": {
            "vulnerability_count": 1,
            "vulnerable_components": [
                {
                    "component_id": "gav://g:a:1",
                    "ecosystem": "maven",
                    "package": "g:a",
                    "version": "1",
                    "cves": ["CVE-2"],
                }
            ],
        },
        "file_results": [
            {
                "dm_type": "gradle",
                "file_path": "build.gradle",
                "display_changes": [{"package": "g:a"}],
                "version_inventory": {
                    "g:a": ["1", "2", "3"],
                },
            }
        ],
    }

    output = write_remediation_evidence(results)
    payload = json.loads(
        tmp_path.joinpath(
            "remediation-evidence.json"
        ).read_text(encoding="utf-8")
    )

    assert output.endswith("remediation-evidence.json")
    assert payload["outcome"] == "Partial"
    assert (
        payload["summary"]["candidate_versions_considered"]
        == 3
    )
    assert (
        payload["summary"]["component_cve_pairs_removed"]
        == 1
    )
    assert (
        payload["summary"]["component_cve_pairs_remaining"]
        == 1
    )

def test_evidence_recommends_bom_for_managed_families(
    tmp_path,
):
    results = {
        "cfg": {"log_dir": str(tmp_path)},
        "verification": {
            "outcome": "Partial",
            "security_status": "still_vulnerable",
        },
        "jfrog_result": {},
        "jfrog_result_after": {
            "vulnerability_count": 1,
            "vulnerable_components": [
                {
                    "component_id": (
                        "gav://com.fasterxml.jackson.core:"
                        "jackson-databind:2.21.2"
                    ),
                    "ecosystem": "maven",
                    "package": (
                        "com.fasterxml.jackson.core:"
                        "jackson-databind"
                    ),
                    "version": "2.21.2",
                    "cves": ["CVE-1"],
                }
            ],
        },
        "file_results": [],
    }

    write_remediation_evidence(results)
    payload = json.loads(
        (tmp_path / "remediation-evidence.json").read_text(
            encoding="utf-8"
        )
    )

    assert any(
        action["category"] == "platform_or_bom"
        for action in payload["next_actions"]
    )
