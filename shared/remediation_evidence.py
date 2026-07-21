from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

_CSV_SOURCES = (
    "gradle-version-changes.csv",
    "gradle-force-overrides.csv",
    "gradle-skipped.csv",
    "gradle-fetch-errors.csv",
    "build-validation-auto-fixes.csv",
    "build-validation-manual-updates.csv",
    "build-validation-external-auto-fixes.csv",
    "build-validation-external-blockers.csv",
    "direct-dependency-version-changes.csv",
    "forced-overrides-changes.csv",
    "forced-overrides-skipped.csv",
    "npm-view-errors.csv",
    "python-version-changes.csv",
    "python-skipped.csv",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    try:
        with path.open(
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except Exception as exc:
        return [{"error": f"Could not read {path.name}: {exc}"}]
def _component_pairs(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for component in audit.get("vulnerable_components", []) or []:
        rows.append(
            {
                "component_id": component.get("component_id", ""),
                "ecosystem": component.get("ecosystem", ""),
                "package": component.get("package", ""),
                "version": component.get("version", ""),
                "cves": sorted(
                    str(cve)
                    for cve in component.get("cves", []) or []
                ),
            }
        )
    return rows

def write_remediation_evidence(
    results: dict[str, Any],
    log_dir: str | None = None,
) -> str:
    cfg = dict(results.get("cfg", {}) or {})
    root = Path(
        log_dir
        or cfg.get("log_dir")
        or results.get("log_dir")
        or "logs"
    )
    root.mkdir(parents=True, exist_ok=True)

    before = dict(results.get("jfrog_result", {}) or {})
    after = dict(results.get("jfrog_result_after", {}) or {})
    verification = dict(results.get("verification", {}) or {})

    file_evidence = []
    total_candidates = 0

    for file_result in results.get("file_results", []) or []:
        inventory = dict(
            file_result.get("version_inventory", {}) or {}
        )
        candidate_counts = {
            package: len(versions)
            for package, versions in inventory.items()
        }
        total_candidates += sum(candidate_counts.values())

        file_evidence.append(
            {
                "file_path": file_result.get("file_path", ""),
                "dependency_manager": file_result.get(
                    "dm_type", ""
                ),
                "write_status": file_result.get(
                    "write_status", ""
                ),
                "validation_status": file_result.get(
                    "validation_status", ""
                ),
                "validation_message": file_result.get(
                    "validation_message", ""
                ),
                "verification_status": file_result.get(
                    "verification_status", ""
                ),
                "test_status": file_result.get(
                    "test_status", ""
                ),
                "selected_changes": list(
                    file_result.get("display_changes", []) or []
                ),
                "skipped": list(
                    file_result.get("skipped_display", []) or []
                ),
                "raw_skipped": list(
                    file_result.get("skipped_raw", []) or []
                ),
                "fetch_errors": list(
                    file_result.get("fetch_errors", []) or []
                ),
                "version_inventory": inventory,
                "candidate_counts": candidate_counts,
            }
        )

    csv_evidence = {
        filename: _read_csv(root / filename)
        for filename in _CSV_SOURCES
        if (root / filename).exists()
    }

    before_components = _component_pairs(before)
    after_components = _component_pairs(after)
    before_pairs = {
        (
            row["component_id"],
            cve,
        )
        for row in before_components
        for cve in row["cves"]
    }
    after_pairs = {
        (
            row["component_id"],
            cve,
        )
        for row in after_components
        for cve in row["cves"]
    }

    payload = {
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "remediation_budget_seconds": 300,
        "failure_isolation_enabled": cfg.get(
            "enable_failure_isolation",
            True,
        ),
        "outcome": verification.get("outcome", ""),
        "classification": verification.get(
            "classification", ""
        ),
        "security_status": verification.get(
            "security_status", ""
        ),
        "test_status": verification.get(
            "test_status", ""
        ),
        "summary": {
            "dependency_files": len(file_evidence),
            "candidate_versions_considered": total_candidates,
            "vulnerability_records_before": before.get(
                "vulnerability_count", 0
            ),
            "vulnerability_records_after": after.get(
                "vulnerability_count", 0
            ),
            "component_cve_pairs_removed": len(
                before_pairs - after_pairs
            ),
            "component_cve_pairs_remaining": len(
                before_pairs & after_pairs
            ),
            "component_cve_pairs_new": len(
                after_pairs - before_pairs
            ),
        },
        "original_cves": verification.get(
            "original_cves", []
        ),
        "remaining_original_cves": verification.get(
            "remaining_original_cves", []
        ),
        "refresh_errors": verification.get(
            "refresh_errors", []
        ),
        "tests": verification.get("tests", {}),
        "before_scan": {
            "json_path": before.get("json_path", ""),
            "components": before_components,
        },
        "after_scan": {
            "json_path": after.get("json_path", ""),
            "components": after_components,
        },
        "files": file_evidence,
        "diagnostic_csvs": csv_evidence,
        "next_actions": _next_actions(
            verification,
            file_evidence,
            csv_evidence,
            after_components,
        ),
    }

    output = root / "remediation-evidence.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return str(output)


def _next_actions(
    verification: dict[str, Any],
    files: list[dict[str, Any]],
    csv_evidence: dict[str, list[dict[str, str]]],
    remaining_components: list[dict[str, Any]],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []

    manual = csv_evidence.get(
        "build-validation-manual-updates.csv",
        [],
    )
    if manual:
        actions.append(
            {
                "priority": "high",
                "category": "build_compatibility",
                "action": (
                    "Review exhaustive-isolation failures and try "
                    "alternative safe versions for the implicated "
                    "packages instead of retaining the rollback."
                ),
            }
        )

    fetch_errors = [
        error
        for file_result in files
        for error in file_result.get("fetch_errors", [])
    ]
    if fetch_errors:
        actions.append(
            {
                "priority": "high",
                "category": "registry_metadata",
                "action": (
                    "Resolve version-metadata lookup failures before "
                    "declaring the package unrecoverable."
                ),
            }
        )

    no_versions = [
        skipped
        for file_result in files
        for skipped in file_result.get("raw_skipped", [])
        if "no versions" in str(
            skipped.get("reason", "")
        ).lower()
    ]
    if no_versions:
        actions.append(
            {
                "priority": "high",
                "category": "candidate_availability",
                "action": (
                    "Confirm the correct Artifactory repository and "
                    "whether internal packages have any published "
                    "fixed versions."
                ),
            }
        )

    remaining_packages = {
        component.get("package", "")
        for component in remaining_components
    }
    managed_families = {
        "jackson": any(
            "jackson" in package
            for package in remaining_packages
        ),
        "netty": any(
            package.startswith("io.netty:")
            for package in remaining_packages
        ),
        "spring": any(
            package.startswith("org.springframework")
            for package in remaining_packages
        ),
        "tomcat": any(
            package.startswith("org.apache.tomcat")
            for package in remaining_packages
        ),
    }
    families = [
        family
        for family, present in managed_families.items()
        if present
    ]
    if families:
        actions.append(
            {
                "priority": "high",
                "category": "platform_or_bom",
                "action": (
                    "Try coordinated platform/BOM upgrades for: "
                    + ", ".join(families)
                    + "."
                ),
            }
        )

    if verification.get("security_status") == "incomplete":
        actions.append(
            {
                "priority": "high",
                "category": "verification",
                "action": (
                    "Regenerate the resolved dependency graph and "
                    "rerun the secondary JFrog scan."
                ),
            }
        )

    if not actions:
        actions.append(
            {
                "priority": "none",
                "category": "complete",
                "action": "No additional remediation action identified.",
            }
        )

    return actions
