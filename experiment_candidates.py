#!/usr/bin/env python3
"""
experiment_candidates.py

Tests two approaches for identifying npm packages from CVE/advisory descriptions:
  A) Candidates: regex + hyphenated-token heuristic → per-task filtered list sent to Claude
  B) Full list: all known packages sent to Claude for all tasks at once

Both approaches use a single batched Claude call (one prompt, all tasks).
Ground truth: OSV-indexed package name.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request

# ── Noise packages: simulate a real project's transitive tree ────────────────
NOISE_PACKAGES: set[str] = {
    "express",
    "react",
    "vue",
    "webpack",
    "typescript",
    "jest",
    "mocha",
    "chai",
    "eslint",
    "prettier",
    "dotenv",
    "uuid",
    "passport",
    "helmet",
    "cors",
    "mongoose",
    "sequelize",
    "winston",
    "debug",
    "chalk",
    "yargs",
    "commander",
    "inquirer",
    "axios",
    "body-parser",
    "compression",
    "cookie-parser",
    "serve-static",
    "mime",
    "mime-types",
    "content-type",
    "fresh",
    "range-parser",
    "bcrypt",
    "mysql2",
    "pg",
    "redis",
    "mongodb",
    "knex",
    "ajv",
    "joi",
    "sharp",
    "svgo",
    "cross-fetch",
    "form-data",
    "multer",
    "busboy",
    "class-validator",
    "@babel/core",
    "@babel/preset-env",
    "@types/node",
    "webpack-cli",
    "node-fetch",
    "whatwg-url",
    "isomorphic-fetch",
    "sinon",
    "ora",
    "underscore",
    "async",
    "request",
    "colors",
    "mysql",
    "multiparty",
    "imagemin",
    "json-schema",
    "moment",
    "socket.io",
    "jsonwebtoken",
    "xml2js",
    "tough-cookie",
}

# ── OSV helpers ──────────────────────────────────────────────────────────────


def osv_query_package(name: str, timeout: int = 15) -> list[str]:
    url = "https://api.osv.dev/v1/query"
    body = json.dumps({"package": {"name": name, "ecosystem": "npm"}}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "experiment/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return [v["id"] for v in data.get("vulns", [])]
    except Exception as exc:
        print(f"  OSV query failed for {name}: {exc}", file=sys.stderr)
        return []


def osv_fetch(vuln_id: str, timeout: int = 15) -> dict | None:
    url = f"https://api.osv.dev/v1/vulns/{vuln_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "experiment/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_npm_package_name(osv_data: dict) -> str | None:
    for affected in osv_data.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("ecosystem", "").lower() == "npm":
            return pkg.get("name") or None
    return None


def get_description(osv_data: dict) -> str:
    parts = []
    if osv_data.get("summary"):
        parts.append(osv_data["summary"])
    if osv_data.get("details"):
        parts.append(osv_data["details"])
    return "\n".join(parts).strip()


# ── Candidate building (mirrors parsers/node.py) ─────────────────────────────


def build_package_patterns(known_packages: set[str]) -> dict[str, re.Pattern]:
    patterns = {}
    for pkg in known_packages:
        escaped = re.escape(pkg)
        patterns[pkg] = re.compile(
            rf"(?<![A-Za-z0-9_@/.-]){escaped}(?![A-Za-z0-9_@/.-])",
            re.IGNORECASE,
        )
    return patterns


def get_candidates(
    text: str, pkg_patterns: dict[str, re.Pattern], known_packages: set[str]
) -> list[str]:
    candidates = [pkg for pkg, pat in pkg_patterns.items() if pat.search(text)]

    # Hyphenated token heuristic: "node-tar" → try "tar"
    for token in re.findall(r"[A-Za-z@][A-Za-z0-9@/_.-]*-[A-Za-z0-9._-]+", text):
        parts = token.lstrip("@").split("/")[-1].split("-")
        for i in range(1, len(parts)):
            seg = "-".join(parts[i:])
            if seg in known_packages and seg not in candidates:
                candidates.append(seg)

    return candidates


# ── Batched Claude caller ─────────────────────────────────────────────────────


def batch_call_claude(
    tasks: list[tuple[int, str, list[str]]],  # (idx, description, pkg_list_for_this_task)
    claude_cmd: str = "claude",
    timeout: int = 120,
) -> dict[int, list[str]]:
    """
    Send all tasks in a single Claude call.
    Each task gets its own pkg_list (either candidates or the full list).
    Since pkg lists differ per task, we embed the list in each task block.

    Returns {idx: [matched_packages]}.
    """
    if not tasks:
        return {}

    task_blocks: list[str] = []
    for i, (_idx, desc, pkg_list) in enumerate(tasks):
        pkg_block = "\n".join(f"  - {p}" for p in sorted(pkg_list))
        task_blocks.append(
            f"Task {i}:\nPackages to consider:\n{pkg_block}\nAdvisory text:\n{desc.strip()}"
        )

    tasks_text = "\n\n---\n\n".join(task_blocks)

    prompt = (
        "You are analyzing security advisory descriptions to identify affected npm packages.\n\n"
        "For each numbered task, a list of candidate packages and an advisory text are provided.\n"
        "Identify which packages from THAT TASK's list are mentioned or clearly referred to "
        "(including by display name, e.g. 'Next.js' refers to 'next', 'node-tar' refers to 'tar').\n\n"
        "Return a JSON object where keys are task numbers (as strings) and values are arrays "
        "of matched package names from that task's list. Use [] if none match.\n"
        'Example: {"0": ["lodash"], "1": [], "2": ["tar", "semver"]}\n\n'
        "Reply with the JSON object only.\n\n"
        f"{tasks_text}"
    )

    cmd = [
        claude_cmd,
        "-p",
        prompt,
        "--model",
        "haiku",
        "--effort",
        "low",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print("  Claude timed out", file=sys.stderr)
        return {}
    except Exception as exc:
        print(f"  Claude call failed: {exc}", file=sys.stderr)
        return {}

    raw = proc.stdout or ""
    json_line = next((line for line in reversed(raw.splitlines()) if line.startswith("{")), None)
    if not json_line:
        print(f"  No JSON in Claude output: {raw[:200]}", file=sys.stderr)
        return {}
    try:
        out = json.loads(json_line)
    except json.JSONDecodeError as exc:
        print(f"  JSON parse error: {exc}", file=sys.stderr)
        return {}
    if out.get("is_error"):
        print(f"  Claude error: {out.get('result', '')[:200]}", file=sys.stderr)
        return {}

    result_text = out.get("result", "")
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", result_text).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
        else:
            return {}

    if not isinstance(parsed, dict):
        return {}

    result: dict[int, list[str]] = {}
    for k, v in parsed.items():
        try:
            chunk_idx = int(k)
        except (ValueError, TypeError):
            continue
        if chunk_idx < len(tasks):
            real_idx, _, pkg_list = tasks[chunk_idx]
            pkg_set = set(pkg_list)
            if isinstance(v, list):
                result[real_idx] = [p for p in v if isinstance(p, str) and p in pkg_set]
            else:
                result[real_idx] = []
    return result


# ── Experiment ────────────────────────────────────────────────────────────────

QUERY_PACKAGES = [
    "lodash",  # exact match expected
    "minimist",  # exact match expected
    "semver",  # exact match expected
    "qs",  # exact match expected
    "tar",  # CVE texts say "node-tar" — heuristic should catch it
    "next",  # CVE texts say "Next.js" — regex/heuristic both miss it
    "marked",  # exact match expected
    "node-forge",  # hyphenated, exact match expected
    "got",  # short name, might appear as "Got" or "node-got"
    "follow-redirects",  # exact match expected
    "word-wrap",  # exact match expected
    "postcss",  # exact match expected
    "url-parse",  # hyphenated, exact match expected
    "tough-cookie",  # hyphenated, exact match expected
    "axios",  # exact match expected
]

ADVISORIES_PER_PACKAGE = 2


def run():
    print("=" * 70)
    print("Experiment: candidates-filtered vs full-list for CVE package ID")
    print("=" * 70)

    # Step 1: collect samples
    samples: list[tuple[str, str, str]] = []  # (vuln_id, gt_package, description)
    seen_ids: set[str] = set()

    print("\nQuerying OSV for advisories…")
    for pkg_name in QUERY_PACKAGES:
        ids = osv_query_package(pkg_name)
        fetched = 0
        for vid in ids:
            if vid in seen_ids or fetched >= ADVISORIES_PER_PACKAGE:
                break
            data = osv_fetch(vid)
            if not data:
                continue
            gt = get_npm_package_name(data)
            if not gt or gt != pkg_name:
                continue
            desc = get_description(data)
            if not desc:
                continue
            seen_ids.add(vid)
            fetched += 1
            samples.append((vid, gt, desc))
            print(f"  {vid}: {gt} ({len(desc)} chars)")
        time.sleep(0.15)

    if not samples:
        print("No samples collected — check network access.", file=sys.stderr)
        sys.exit(1)

    print(f"\nCollected {len(samples)} samples.")

    # Step 2: build known_packages
    gt_packages: set[str] = {gt for _, gt, _ in samples}
    known_packages: set[str] = NOISE_PACKAGES | gt_packages
    pkg_patterns = build_package_patterns(known_packages)
    full_pkg_list = sorted(known_packages)

    print(
        f"Known packages: {len(known_packages)} total ({len(gt_packages)} ground-truth + {len(NOISE_PACKAGES)} noise)"
    )

    # Step 3: build per-sample candidates
    sample_candidates: list[list[str]] = []
    for _vid, _gt, desc in samples:
        cands = get_candidates(desc, pkg_patterns, known_packages)
        sample_candidates.append(cands)

    # Step 4: single batched Claude call for approach A (candidates)
    print("\nApproach A: batched call with per-task candidate lists…")
    a_tasks = [(i, desc, sample_candidates[i]) for i, (_, _, desc) in enumerate(samples)]
    a_results = batch_call_claude(a_tasks)

    # Step 5: single batched Claude call for approach B (full list)
    print("Approach B: batched call with full package list for all tasks…")
    b_tasks = [(i, desc, full_pkg_list) for i, (_, _, desc) in enumerate(samples)]
    b_results = batch_call_claude(b_tasks)

    # Step 6: score and print
    print(f"\n{'ID':<35} {'GT':<18} {'Cands':>5} {'GT∈C':>5}  {'A':>3}  {'B':>3}")
    print("─" * 72)

    rows = []
    for i, (vid, gt, _desc) in enumerate(samples):
        candidates = sample_candidates[i]
        in_cands = gt in candidates
        a_found = a_results.get(i, [])
        b_found = b_results.get(i, [])
        a_hit = gt in a_found
        b_hit = gt in b_found

        rows.append(
            {
                "id": vid,
                "gt": gt,
                "candidates": candidates,
                "in_candidates": in_cands,
                "a_found": a_found,
                "b_found": b_found,
                "a_hit": a_hit,
                "b_hit": b_hit,
            }
        )

        print(
            f"{vid:<35} {gt:<18} {len(candidates):>5} {'✓' if in_cands else '✗':>5}  "
            f"{'✓' if a_hit else '✗':>3}  {'✓' if b_hit else '✗':>3}"
        )

    total = len(rows)
    a_hits = sum(r["a_hit"] for r in rows)
    b_hits = sum(r["b_hit"] for r in rows)
    gt_in_cands = sum(r["in_candidates"] for r in rows)
    missed = [r for r in rows if not r["in_candidates"]]

    print(f"\n{'─' * 72}")
    print(f"Samples:                            {total}")
    print(
        f"GT in candidates (regex+heuristic): {gt_in_cands}/{total}  ({100 * gt_in_cands // total if total else 0}%)"
    )
    print(
        f"A (per-task candidates → Claude):   {a_hits}/{total}  ({100 * a_hits // total if total else 0}%)"
    )
    print(
        f"B (full list → Claude):             {b_hits}/{total}  ({100 * b_hits // total if total else 0}%)"
    )

    if missed:
        print(f"\nCases where regex missed GT ({len(missed)}) — only B can possibly recover:")
        for r in missed:
            print(
                f"  {r['id']}: gt={r['gt']}  candidates={r['candidates'][:5]}  A={'✓' if r['a_hit'] else '✗'}  B={'✓' if r['b_hit'] else '✗'}"
            )

    with open("experiment_candidates_results.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, default=str)
    print("\nFull results saved to experiment_candidates_results.json")


if __name__ == "__main__":
    run()
