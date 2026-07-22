# Pipeline Flow

```mermaid
flowchart TD
    SHIM["pipeline/node.py\npipeline/gradle.py\npipeline/python.py"]

    SHIM --> RA["run_analysis(manager, file_path, log_dir, cve_packages, cfg)"]

    RA --> PARSE["parser.parse(file_path)\n─────────────────────\nnpm   → read package.json, collect direct entries\ngradle → read build.gradle, extract dep declarations\npython → read requirements.txt / pyproject.toml"]

    PARSE --> TREE["parser.resolve_tree(parsed, cfg, log_dir)\n─────────────────────\nnpm    → generate / load package-lock.json\ngradle → run 'gradle dependencies' for 4 configurations\npython → run 'pip inspect' and write dependency tree log"]

    TREE --> PKGS["manager.packages_to_fetch(parsed, tree, cve_packages)\n─────────────────────\nfilter CVE targets to packages actually present\nin the lockfile / build file / requirements"]

    PKGS --> FETCH["registry.fetch_versions(packages, cfg)\n─────────────────────\nnpm    → npm view (parallel workers)\ngradle → Artifactory maven-metadata.xml (parallel workers)\npython → pip index versions (serial)"]

    FETCH --> APPLY["output.apply_updates(parsed, tree, versions, cve_packages, cfg)\n─────────────────────\ncompute direct changes, overrides / force entries\nskip packages already at a safe version\nreturn EcosystemUpdateResult"]

    APPLY --> LOGS["output.write_logs(log_dir, result)\n─────────────────────\nwrite CSVs: version-changes, skipped, fetch-errors\nnpm    → also writes npm-available-versions.txt\ngradle → also writes gradle-force-overrides.csv"]

    LOGS --> OUT[/"{ display_changes, skipped_display, file_path, ...extra }"/]
```

# Write, Validate & Rollback

```mermaid
flowchart TD
    OUT[/"analysis result\n{ display_changes, force_entries, ...extra }"/] --> WRITE["output.write_*_file()\n─────────────────────\napply changes to build.gradle / package.json / requirements.txt\nback up the original (.bak) first"]

    WRITE --> BUILD1{"build_fn()\nnpm install / gradle test (light probe) / pip install"}

    BUILD1 -->|passes| CONFIRM{"confirm_fn()\nGradle only: full 'gradle build'\nre-validates a light probe pass before accepting it"}
    CONFIRM -->|passes| SUCCESS(["Success\nclear stale validation CSVs"])
    CONFIRM -->|fails| ISOL

    BUILD1 -->|fails| BASELINE{"Gradle: rebuild with the ORIGINAL file\nsame failing test(s) as before remediation?"}
    BASELINE -->|yes, pre-existing| KEEP(["Keep updates\nrecord build-validation-preexisting-failures.csv"])
    BASELINE -->|no, or n/a| ISOL

    ISOL["enable_failure_isolation?\n(off in Phase 1, on in Phase 2)"] -->|disabled| MANUAL(["Manual Update Required\nfull revert, BuildValidationManualUpdatesError"])
    ISOL -->|enabled| TRIALS["_run_candidate_trials()\n─────────────────────\nrank candidates by relevance to the failure text\ntry stepping down to an intermediate version first\n(≤2 steps, preserves partial CVE fix)\nfall back to full single-package revert\naccumulate reverts until the build passes"]

    TRIALS -->|found minimal revert set| PARTIAL(["Partial\nsome CVEs fixed, some reverted — write auto-fixes.csv"])
    TRIALS -->|nothing works| MANUAL

    SUCCESS --> VERIFY
    KEEP --> VERIFY
    PARTIAL --> VERIFY
    MANUAL --> VERIFY["finalize_verification()\n─────────────────────\nrerun tests, secondary JFrog audit\nnode: rerun tests against pre-remediation package.json\n(git HEAD) — same failure there ⇒ treated as pre-existing\ntraceback persisted to verification-error.txt on any exception"]

    VERIFY --> REPORT["report.py\nOverall Status driven by verification.outcome\n(Success 🟢 / Partial 🟡 Needs Review / Failed·Error 🔴)"]

    REPORT --> PHASE2{"Phase 2 replay requested?\n(--phase2-results)"}
    PHASE2 -->|checkout still on disk| REPLAY["re-run write+validate with\nenable_failure_isolation=True"]
    PHASE2 -->|checkout missing — reused/cleaned indexed dir| RECLONE["re-clone to the recorded checkout_dir\n(same path, same repo name)"] --> REPLAY
    REPLAY --> REPORT
```

# Version Determination

How `APPLY` (`output.apply_updates`) picks the actual version number for a flagged
package. All three ecosystems share the same underlying safety check
(`shared.version_search.find_safe_version`); each just builds its own candidate
lists and its own `is_accessible` probe around it.

## Shared core: `find_safe_version`

```mermaid
flowchart TD
    START(["forward_candidates, backward_candidates\n(order = preference, e.g. ascending from current)"]) --> CVEFWD["shared.xray.filter_versions_without_cves(forward)\nbatch-query Xray per candidate version,\ndrop any still CVE-flagged"]
    CVEFWD --> PROBEFWD["probe_candidates_concurrently(forward, is_accessible)\nall candidates probed in parallel (≤8 workers);\nfirst accessible one BY LIST ORDER wins —\nlater probes cancelled once an earlier one succeeds,\nbut earlier in-flight probes are always awaited"]
    PROBEFWD -->|found| RESULT(["return version, empty diagnostic"])
    PROBEFWD -->|none accessible| CVEBACK["filter_versions_without_cves(backward)\n(only paid for when forward comes up empty —\nan extra Xray round-trip skipped in the common case)"]
    CVEBACK --> PROBEBACK["probe_candidates_concurrently(backward, is_accessible)"]
    PROBEBACK -->|found| RESULT
    PROBEBACK -->|none| NONE(["return None, diagnostic\n(counts of CVE-filtered + inaccessible candidates)"])
```

## Gradle (`output/gradle.py::apply_updates`)

```mermaid
flowchart TD
    KEY["JFrog-flagged package (group:artifact)"] --> TARGET["target = select_best_version(remediation_versions, available, major, constraint, current)\nsame-minor-first if remediation mentions the current\nminor line, else same-major; never crosses major;\nconstraint '>' picks the LOWEST candidate above current\n(minimal safe bump, not latest)"]

    TARGET --> ACCESS0{"skip_block_check?"}
    ACCESS0 -->|no| PROBE0["find_accessible_version(group, artifact, target, available, ...)\n= find_safe_version with forward: same major, ≥ target (top 10, no prereleases)\nbackward: same major, < target (top 10)\nis_accessible = registry.maven.version_accessible:\nHEAD .module (403 ⇒ definitely blocked) →\nGET .jar streamed, status only (NOT HEAD —\nXray's download-policy block only fires on a\nreal GET, confirmed live on jackson-databind) →\nGET .pom, accept only if packaging=pom (BOM/parent)"]
    PROBE0 -->|none accessible| SKIPT(["skipped: no accessible version found >= target"])
    PROBE0 -->|found| TARGET2["target = accessible version"]
    ACCESS0 -->|yes| TARGET2

    TARGET2 --> DIRECT{"key in direct_by_key?\n(declared in build.gradle)"}

    DIRECT -->|yes: Case 1| OCC["patch EVERY parsed occurrence of this\ngroup:artifact in the file — not just the first\n(a build.gradle can declare the same artifact twice;\nthe writer used to only patch the first textual match)"]
    OCC --> CHANGE(["change: direct dependency edit"])

    DIRECT -->|no| PARENT{"parents_of[key] non-empty?\n(Case 2: transitive)"}
    PARENT -->|yes| CASE2["resolve_transitive_with_gradle:\nbump ONE parent, highest-version candidate first,\nreal 'gradle dependencies' in a temp copy;\ncapped at 1 probe total across ALL parents for this\nkey (0/275 lower candidates ever succeeded in real\nbatch data — trying more just burned ~40-60s each)"]
    CASE2 -->|resolves it| CHANGE
    CASE2 -->|fails| CASE3
    PARENT -->|no| CASE3["Case 3: resolutionStrategy.force entry"]
    CASE3 --> FORCE(["force entry"])

    CHANGE --> SIBLING
    FORCE --> SIBLING["_sibling_family_forces:\nany OTHER same-group artifact currently at the\nEXACT SAME resolved version as the one just changed\nis treated as version-locked and forced to match —\nbut ONLY to a version confirmed to exist for THAT\nsibling (checked against available_by_key); falls back\nto the closest existing version below the trigger's\ntarget, or skips the sibling entirely if nothing exists\n(jackson-annotations has no patch releases, so it can't\njust inherit jackson-databind's exact '2.22.1')"]
    SIBLING --> COMPETE["_align_competing_pins:\nre-scan the WHOLE file for any other declaration\n(strict version block or resolutionStrategy.force line)\nof a package now in changes/force_entries that's\nstill pinned to something else — realign it too"]
    COMPETE --> WRITE(["write_gradle_file: changes, then forces, then\nSpring Boot managed properties / plugin version /\ndependency substitutions"])
```

## Node (`output/node.py::apply_updates`)

```mermaid
flowchart TD
    PKG["JFrog-flagged package, per major version present"] --> SELECT["selected = select_best_version(remediation_versions, available, major, constraint)\nor minimum_required if nothing found\n(same shared algorithm as Gradle)"]

    SELECT --> VERIFY{"skip_block_check?"}
    VERIFY -->|no| SAFE["find_safe_version over the same-major range\naround `selected` (forward: selected..max,\nbackward: < selected), is_accessible =\nregistry.npm.is_version_blocked (npm pack probe)\n— this now runs for EVERY selection, not just ones\nalready known registry-blocked (the fold added this\nsession: previously an accessible-but-still-CVE-\nflagged pick like dompurify/fast-uri/js-yaml shipped\nunverified, because nothing asked Xray about it)"]
    SAFE -->|different version verified| SUBSTITUTE["selected = verified version\nrecord in block_changes"]
    SAFE -->|nothing better found| KEEP["keep original `selected` as-is —\nnever drop the major; several write paths below\nassume every major has a selected_by_major entry"]
    VERIFY -->|yes| KEEP

    SUBSTITUTE --> ROUTE
    KEEP --> ROUTE{"where does this package live?"}
    ROUTE -->|direct dependency| DIRECTW(["update dependencies/devDependencies spec;\nremove any now-superseded flat override"])
    ROUTE -->|transitive, single major| PARENTW(["bump a direct parent's spec,\nverified via npm install --package-lock-only"])
    ROUTE -->|transitive, multiple majors| NESTEDW(["nested overrides keyed by\nlockfile-resolved top-level dependents"])
    ROUTE -->|no direct dep, no clean parent bump| FLATW(["flat overrides entry (global force)"])
```

## Python (`managers/python.py::apply_updates`)

```mermaid
flowchart TD
    REQ["JFrog-flagged package in requirements.txt / pyproject.toml"] --> CONSTRAIN["keep registry versions matching the\ndeclared constraint, e.g. at least 1.2 and below 2.0"]
    CONSTRAIN -->|none satisfy| SKIP(["skipped: no registry version satisfies constraint"])
    CONSTRAIN --> SPLIT["forward = same major, above current\nbackward = next major up\n(PyPI search never considers a downgrade\nbelow current, unlike Maven/npm's true\nforward/backward-of-target search)"]

    SPLIT --> BLOCKCHECK{"skip_block_check?"}
    BLOCKCHECK -->|yes| FIRST["candidate = first of forward, else backward"]
    BLOCKCHECK -->|no| SAFE["find_safe_version(forward, backward, is_accessible)\nis_accessible = registry.pypi.is_version_blocked:\npip download pkg==version --no-deps --dest a temp dir\n403 / 404 / forbidden / 'no matching distribution'\nin stderr ⇒ blocked"]

    FIRST --> RESULT{"candidate found?"}
    SAFE --> RESULT
    RESULT -->|no| SKIP2(["skipped: no safe version found in registry"])
    RESULT -->|== current version| NOOP(["no change"])
    RESULT -->|new version| CHANGE(["change: update requirement line"])
```
