from __future__ import annotations

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# Match CVE-YYYY-NNNNN and GHSA-XXXX-XXXX-XXXX in task titles
_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_GHSA_RE = re.compile(r"\bGHSA-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}\b", re.IGNORECASE)

# Extracts the upper bound from NVD version strings like "< 1.2.3" or ">= 1.0.0, < 1.2.3"
_UPPER_BOUND_RE = re.compile(r"<\s*([\d][^\s,]*)")


def extract_advisory_id(title: str) -> str | None:
    """Return the first CVE or GHSA ID found in title, or None.

    CVE IDs are uppercased (always uppercase by convention).
    GHSA IDs preserve original case — OSV is case-sensitive for the hex segments.
    """
    m = _GHSA_RE.search(title)
    if m:
        return m.group(0)
    m = _CVE_RE.search(title)
    if m:
        return m.group(0).upper()
    return None


def lookup_osv(advisory_id: str, timeout: int = 10) -> dict | None:
    """Query api.osv.dev for advisory_id. Returns parsed JSON or None on any error."""
    url = f"https://api.osv.dev/v1/vulns/{advisory_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "package-update-tool/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_fixed_versions(osv_data: dict, ecosystem: str) -> dict[str, list[str]]:
    """Return {package_name: [fixed_version, ...]} for the given ecosystem.

    For Maven the name is 'group:artifact'. For npm it is the bare package name.
    Multiple SEMVER ranges on the same package produce multiple fixed versions
    (e.g. one fix per major branch).
    """
    result: dict[str, list[str]] = {}
    for affected in osv_data.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("ecosystem", "").lower() != ecosystem.lower():
            continue
        name = pkg.get("name", "")
        if not name:
            continue
        for r in affected.get("ranges", []):
            for event in r.get("events", []):
                fv = event.get("fixed")
                if fv:
                    result.setdefault(name, []).append(fv)
    return result


def _lookup_nvd(cve_id: str, timeout: int) -> dict | None:
    """Query the NVD 2.0 API. Returns the inner cve dict or None."""
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "package-update-tool/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            vulns = data.get("vulnerabilities", [])
            return vulns[0]["cve"] if vulns else None
    except Exception:
        return None


def _get_fixed_versions_from_nvd(nvd_cve: dict, ecosystem: str) -> dict[str, list[str]]:
    """Extract {package: [fixed_version, ...]} from an NVD CVE dict.

    Only reads entries sourced from security-advisories@github.com, which carry
    clean package names. Other sources (Red Hat CPE entries, etc.) are ignored.

    Version strings can be plain "< X.Y.Z" or compound ">= A, < B" — the upper
    bound is extracted in both cases. Multiple affected ranges on the same package
    each contribute their own fixed version.

    Ecosystem heuristic: Maven coordinates contain ':' (group:artifact); npm names do not.
    """
    result: dict[str, list[str]] = {}
    for source_entry in nvd_cve.get("affected", []):
        if source_entry.get("source") != "security-advisories@github.com":
            continue
        for entry in source_entry.get("affectedData", []):
            product = entry.get("product", "")
            if not product:
                continue
            is_maven = ":" in product
            if ecosystem.lower() == "maven" and not is_maven:
                continue
            if ecosystem.lower() == "npm" and is_maven:
                continue
            for ver_info in entry.get("versions", []):
                if ver_info.get("status") != "affected":
                    continue
                m = _UPPER_BOUND_RE.search(ver_info.get("version", ""))
                if m:
                    result.setdefault(product, []).append(m.group(1))
    return result


def resolve_advisory(advisory_id: str, ecosystem: str, timeout: int = 10) -> dict[str, list[str]]:
    """Look up advisory_id and return {package: [fixed_version, ...]} for the ecosystem.

    Resolution order:
    1. OSV direct lookup
    2. Chase GHSA aliases from the OSV response (CVE entries often lack package metadata)
    3. NVD API fallback for CVEs not yet indexed in OSV
    """
    data = lookup_osv(advisory_id, timeout)
    if data:
        result = get_fixed_versions(data, ecosystem)
        if result:
            return result

        for alias in data.get("aliases", []):
            if not alias.upper().startswith("GHSA-"):
                continue
            alias_data = lookup_osv(alias, timeout)
            if not alias_data:
                continue
            alias_result = get_fixed_versions(alias_data, ecosystem)
            if alias_result:
                return alias_result

    if advisory_id.upper().startswith("CVE-"):
        nvd_data = _lookup_nvd(advisory_id, timeout)
        if nvd_data:
            return _get_fixed_versions_from_nvd(nvd_data, ecosystem)

    return {}


def prefetch_advisories(
    rows: list[tuple[int | None, str, str]],
    ecosystem: str,
    workers: int = 8,
    timeout: int = 10,
) -> dict[str, dict[str, list[str]]]:
    """Look up all advisory IDs found in task titles in parallel.

    Scans every (task_id, title, text) row for CVE/GHSA IDs, deduplicates them,
    fetches all in parallel, prints one status line per unique ID as each result
    arrives, and returns a cache dict {advisory_id: {package: [fixed_version, ...]}}
    for the caller to commit from.
    """
    from shared.utils import ProgressBar

    unique_aids: list[str] = list(
        {aid for _, title, _ in rows for aid in [extract_advisory_id(title)] if aid}
    )
    cache: dict[str, dict[str, list[str]]] = {}
    if not unique_aids:
        return cache

    progress = ProgressBar(len(unique_aids), "Looking up advisories (OSV/NVD)")
    with ThreadPoolExecutor(max_workers=min(len(unique_aids), workers)) as ex:
        futures = {ex.submit(resolve_advisory, aid, ecosystem, timeout): aid for aid in unique_aids}
        for fut in as_completed(futures):
            aid = futures[fut]
            pkg_fixed = fut.result()
            cache[aid] = pkg_fixed
            progress.update()
            status = (
                ", ".join(f"{p}>={','.join(vs)}" for p, vs in pkg_fixed.items())
                if pkg_fixed
                else f"no {ecosystem} packages, falling back to NLP"
            )
            print(f"  OSV: {aid} — {status}")

    return cache
