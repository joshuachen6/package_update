from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentVersion:
    ecosystem: str
    package: str
    version: str

def _strip_jfrog_service_path(host):
    for suffix in ("/artifactory", "/xray"):
        if host.endswith(suffix):
            return host[: -len(suffix)]
    return host


def _normalize_xray_host(host):
    if not host:
        return None
    host = host.strip().rstrip("/")
    if not host:
        return None
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    return _strip_jfrog_service_path(host)


def _component_id(component):
    if component.ecosystem == "npm":
        return f"npm://{component.package}:{component.version}"
    if component.ecosystem == "maven":
        group, artifact = component.package.split(":", 1)
        return f"gav://{group}:{artifact}:{component.version}"
    return f"{component.ecosystem}://{component.package}:{component.version}"
def _extract_cves(payload):
    cves = []

    def walk(value):
        if isinstance(value, dict):
            for key in ("cve", "cve_id", "cveId", "id"):
                cve = value.get(key)
                if (
                    isinstance(cve, str)
                    and cve.upper().startswith("CVE-")
                    and cve not in cves
                ):
                    cves.append(cve)

            for key in ("cves", "vulnerabilities", "vulns", "issues"):
                child = value.get(key)
                if isinstance(child, list):
                    for item in child:
                        if (
                            isinstance(item, str)
                            and item.upper().startswith("CVE-")
                            and item not in cves
                        ):
                            cves.append(item)

            for child in value.values():
                walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return cves


def _component_has_cves(entry):
    if not isinstance(entry, dict):
        return False
    for key in ("cves", "vulnerabilities", "vulns", "issues"):
        direct = entry.get(key)
        if isinstance(direct, list) and direct:
            return True
    return bool(_extract_cves(entry))


def _entry_component_id(entry):
    if not isinstance(entry, dict):
        return None

    for key in (
        "component_id",
        "component",
        "componentId",
        "component_id_or_path",
        "id",
    ):
        value = entry.get(key)
        if isinstance(value, str) and "://" in value:
            return value
    component = entry.get("component")
    if isinstance(component, dict):
        for key in ("component_id", "componentId", "id"):
            value = component.get(key)
            if isinstance(value, str) and "://" in value:
                return value

    return None


def _iter_result_entries(payload):
    results = payload.get("results", payload) if isinstance(payload, dict) else payload

    if isinstance(results, dict):
        for component_id, entry in results.items():
            if isinstance(entry, dict):
                yield str(component_id), entry
            elif isinstance(entry, list):
                yield str(component_id), {"cves": entry}
    elif isinstance(results, list):
        for entry in results:
            if not isinstance(entry, dict):
                continue

            component_id = _entry_component_id(entry)
            if component_id:
                yield component_id, entry
                continue

            nested_results = entry.get("results")
            if isinstance(nested_results, dict):
                for nested_component_id, nested_entry in nested_results.items():
                    if isinstance(nested_entry, dict):
                        yield str(nested_component_id), nested_entry
                    elif isinstance(nested_entry, list):
                        yield str(nested_component_id), {"cves": nested_entry}
def search_cves_by_components(
    components,
    xray_host=None,
    auth=None,
    timeout=30,
):
    host = _normalize_xray_host(xray_host or os.environ.get("JFROG_XRAY_HOST"))
    if not host or not components:
        return {}, ""

    component_ids = [_component_id(component) for component in components]
    body = json.dumps({"components_id": component_ids}).encode("utf-8")

    request = urllib.request.Request(
        f"{host}/xray/api/v1/component/searchCvesByComponents",
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "package-update-tool/1.0",
        },
        method="POST",
    )

    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    elif os.environ.get("JFROG_ACCESS_TOKEN"):
        request.add_header("Authorization", f"Bearer {os.environ['JFROG_ACCESS_TOKEN']}")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        suffix = f": {detail[:500]}" if detail else ""
        return {}, f"Xray CVE lookup HTTP {exc.code}{suffix}"
    except json.JSONDecodeError as exc:
        return {}, f"Xray CVE lookup returned invalid JSON: {exc}"
    except Exception as exc:
        return {}, f"Xray CVE lookup failed: {exc}"

    by_component = {}
    for component_id, entry in _iter_result_entries(payload):
        if _component_has_cves(entry):
            cves = _extract_cves(entry)
            by_component[str(component_id)] = cves or ["CVE"]

    return by_component, ""
def filter_versions_without_cves(
    ecosystem,
    package,
    versions,
    xray_host=None,
    auth=None,
    timeout=30,
):
    if not versions:
        return [], {}, ""

    components = [
        ComponentVersion(ecosystem=ecosystem, package=package, version=str(version))
        for version in versions
    ]

    vulnerable_components, error = search_cves_by_components(
        components,
        xray_host=xray_host,
        auth=auth,
        timeout=timeout,
    )

    if error or not vulnerable_components:
        return versions, vulnerable_components, error

    vulnerable_versions = {
        component.version
        for component in components
        if _component_id(component) in vulnerable_components
    }
    safe_versions = [version for version in versions if str(version) not in vulnerable_versions]
    return safe_versions, vulnerable_components, ""
