"""Overall Status must reflect the verified end state, not CSV file presence.

Seen live in the 2026-07-19 batch: ins-cp-mgmt-admin-api verified
"Success - build passed; no CVEs remain" but was labeled Manual Update
Required because an auto-fixes row existed, while dnc-publish-api was
labeled Success despite verification finding 31 remaining CVE records.
"""

from __future__ import annotations

import csv

from shared import report


def _generate(tmp_path, verification, with_auto_fixes=False):
    if with_auto_fixes:
        with (tmp_path / "build-validation-auto-fixes.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["package", "change_type", "old", "new", "status", "reason"],
            )
            writer.writeheader()
            writer.writerow({
                "package": "ch.qos.logback:logback-core",
                "change_type": "gradle",
                "old": "1.5.25",
                "new": "1.5.38",
                "status": "auto_rolled_back",
                "reason": "build passed after single-package rollback",
            })

    result = {
        "github_url": "",
        "cfg": {"log_dir": str(tmp_path), "proj_dir": ""},
        "jfrog_result": {},
        "file_results": [],
    }
    if verification is not None:
        result["verification"] = verification

    report.generate_report(result, log_dir=tmp_path)
    return (tmp_path / "task-completion-report.md").read_text(encoding="utf-8")


def test_verified_success_outranks_auto_fixes_rows(tmp_path):
    text = _generate(
        tmp_path,
        {"outcome": "Success", "classification": "Success - build passed; no CVEs remain"},
        with_auto_fixes=True,
    )
    assert "🟢 Success" in text
    assert "Manual Update Required" not in text


def test_verified_partial_outranks_clean_csv_state(tmp_path):
    text = _generate(
        tmp_path,
        {"outcome": "Partial", "classification": "Partial - build passed but 31 CVE record(s) remain"},
    )
    assert "🟡 Needs Review" in text
    assert "🟢 Success" not in text


def test_verified_failure_is_manual_update_required(tmp_path):
    text = _generate(tmp_path, {"outcome": "Failed", "classification": "Failed - tests did not pass"})
    assert "🔴 Manual Update Required" in text


def test_csv_presence_fallback_when_no_verification(tmp_path):
    text = _generate(tmp_path, None, with_auto_fixes=True)
    assert "🔴 Manual Update Required" in text
