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
def _normalize_xray_host(host):
    if not host:
        return None
    host = host.strip().rstrip("/")
    if not host:
        return None
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    return host


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
            cve = value.get("cve") or value.get("cve_id") or value.get("id")
            if (
                isinstance(cve, str)
                and cve.upper().startswith("CVE-")
                and cve not in cves
            ):
                cves.append(cve)
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
    direct = entry.get("cves")
    if isinstance(direct, list) and direct:
        return True
    return bool(_extract_cves(entry))


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
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return {}, f"Xray CVE lookup HTTP {exc.code}"
    except Exception as exc:
        return {}, f"Xray CVE lookup failed: {exc}"

    results = payload.get("results", payload)
    by_component = {}

    if isinstance(results, dict):
        iterable = list(results.items())
    elif isinstance(results, list):
        iterable = []
        for entry in results:
            if not isinstance(entry, dict):
                continue
            component_id = (
                entry.get("component_id")
                or entry.get("component")
                or entry.get("componentId")
                or entry.get("id")
            )
            if isinstance(component_id, str):
                iterable.append((component_id, entry))
    else:
        iterable = []

    for component_id, entry in iterable:
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
