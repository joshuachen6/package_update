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
    PHASE2 -->|checkout missing\n(reused/cleaned indexed dir)| RECLONE["re-clone to the recorded checkout_dir\n(same path, same repo name)"] --> REPLAY
    REPLAY --> REPORT
```
