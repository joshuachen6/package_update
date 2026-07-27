# Package Update

JFrog-driven dependency remediation for npm, Gradle, and Python (pip) projects.

The workflow is intentionally simple:

1. Scan dependency files (`package.json`, `build.gradle`, `requirements.txt`/`pyproject.toml`).
2. Generate dependency context:
   - npm lockfile data for Node.js projects.
   - Gradle dependency tree data for Gradle projects.
   - Resolved package versions for Python projects.
3. Run a JFrog Xray CVE audit against resolved components.
4. Use vulnerable package names/coordinates reported by JFrog as the remediation source of truth.
5. Update direct dependencies, npm overrides, Gradle declarations/`resolutionStrategy.force` entries/BOM-managed properties, or Python requirement lines as needed.
6. Validate the build and roll back on failure (optionally isolating just the breaking package instead of reverting everything).

Package identity comes entirely from JFrog findings — there is no legacy task-based or NLP package resolution.

## Requirements

- Python 3.13+
- npm, when remediating Node.js projects
- Gradle or a project Gradle wrapper, when remediating Gradle projects
- pip, when remediating Python projects
- JFrog Artifactory/Xray access
- PyQt6, only needed for the GUI (`make gui`) or the CLI's interactive "quick" window (see below)

## Setup

    make install

Creates a `.venv` and installs the package (plus dev extras: pytest, ruff, mypy) from `pyproject.toml`.

## Configuration

Set these environment variables, or pass the equivalent `--artifactory-*` CLI options:

    export ARTIFACTORY_SOURCE="https://your-jfrog.example.com"
    export ARTIFACTORY_REPO="ins-cp-mgmt-gradle-virtual"
    export ARTIFACTORY_USERNAME="..."
    export ARTIFACTORY_PASSWORD="..."

`ARTIFACTORY_SOURCE` is the JFrog base URL for Xray CVE audit calls and Gradle/Python metadata lookup. `ARTIFACTORY_REPO` is the Maven repository used for Gradle version metadata.

## GUI

    make gui

Opens the full PyQt6 app (`gui.py`): Log / Changes / CVEs tabs for a single project, plus a **Batch** tab that reads a spreadsheet of repo URLs (or a directory of already-cloned repos) and runs remediation across all of them, writing one `logs/batch/<repo>_<branch>/logs/` directory per target. When the batch finishes, a popup summarizes repos processed/successful/partial/failed, full and useful remediation rates, unique vs. total (duplicate-counted) CVEs cleared, vulnerable-package before/after/clearance-rate, and average repo fix time — the same summary plus a per-repo time breakdown is appended to `logs/batch/batch-summary.log`.

## CLI

    make quick

Runs `quick_update.py` with no arguments (current directory as the project). Pass options directly to target a specific project or repo:

    python3 quick_update.py --project-dir /path/to/project

If stdout is a terminal, `quick_update.py` opens a lightweight PyQt6 "quick" window (`ui/quick_window.py`) instead of running headless; pipe/redirect output (e.g. in CI) to force the plain CLI path.

Target explicit files instead of scanning the project directory:

    python3 quick_update.py \
      --project-dir /path/to/project \
      --package-json /path/to/project/package.json \
      --build-file /path/to/project/build.gradle \
      --python-file /path/to/project/requirements.txt

Clone a repo first instead of pointing at a local checkout:

    python3 quick_update.py \
      --github-url https://github.com/org/repo.git \
      --branch main \
      --checkout-dir /path/to/checkouts

Useful options:

    python3 quick_update.py \
      --project-dir /path/to/project \
      --artifactory-source "$ARTIFACTORY_SOURCE" \
      --artifactory-repo "$ARTIFACTORY_REPO" \
      --artifactory-username "$ARTIFACTORY_USERNAME" \
      --artifactory-password "$ARTIFACTORY_PASSWORD" \
      --workers 8 \
      --npm-timeout 90 \
      --gradle-timeout 30 \
      --pip-timeout 90

Other flags:

- `--skip-block-check` — skip the registry-accessibility/CVE re-check on the selected version (faster, less safe).
- `--skip-build-validation` — write updates without running npm/Gradle/pip validation or rollback at all.
- `--enable-failure-isolation` / `--no-enable-failure-isolation` — on build failure, try to isolate and roll back just the breaking package(s) instead of reverting everything. Off by default; a `--phase2-results` replay turns it on explicitly.
- `--capture-build-logs` — run one extra full build against the pre-remediation file, purely to leave `build-log-before.txt`/`build-log-after.txt` artifacts. Adds a full build per repo; meant for verification runs, not routine batches.
- `--phase2-results <path>` — replay a previously written result file with failure isolation enabled (re-clones the checkout if it's no longer on disk).
- `--input-cves <CVE-1,CVE-2,...>` — comma-separated CVE IDs to track/report on, in addition to whatever JFrog reports.

## npm remediation

- Loads or generates `package-lock.json`.
- Runs the JFrog audit on resolved npm components.
- Uses JFrog vulnerable package names to build remediation criteria from the currently installed lockfile version.
- Queries available npm versions and finds the lowest safe (CVE-clear, registry-accessible) version per flagged major.
- Updates direct dependencies, or `overrides`/nested overrides when there's no clean direct/parent bump.
- Runs registry-accessibility + CVE re-verification on the selected version unless `--skip-block-check` is used.
- Validates the project (`npm install`, then `npm run build` if present) and rolls back on failure.

## Gradle remediation

- Parses declared dependencies from `build.gradle` (bare, map-notation, and parenthesized GAV-string forms).
- Resolves dependency trees across common configurations, proactively forcing any Xray-blocked transitive found in the post-change tree before the real build runs.
- Runs the JFrog audit on resolved Maven components.
- Uses JFrog vulnerable Maven coordinates as the remediation source of truth; the version chosen is re-verified for registry accessibility (HTTP GET, not HEAD — Xray's download-policy block only fires on a real GET) unless `--skip-block-check` is used.
- Updates direct dependency declarations when possible (every occurrence, including `version { strictly(...) }` blocks).
- Updates a direct parent for transitive dependencies when that resolves the vulnerable child.
- Adds `resolutionStrategy.force` entries (project and buildscript scope) when a direct update isn't possible, and keeps version-locked sibling artifacts (Netty, Spring, Jackson, ...) and pre-existing competing pins — including `capabilitiesResolution.withCapability { select(...) }` — in sync with the chosen version.
- Validates the Gradle project (`gradle build`, with a lighter `test` probe during isolation search) and rolls back on failure, or isolates just the breaking package(s) when `--enable-failure-isolation` is set.

## Python remediation

- Parses `requirements.txt`/`requirements-*.txt`/`constraints.txt`/`pyproject.toml`.
- Filters available PyPI versions to ones matching the declared constraint and free of the flagged CVEs.
- Updates the requirement line to the selected version.
- Validates via `pip install` and rolls back on failure.

## Logs

Logs are written under `<project-dir>/logs` by default (or `logs/batch/<repo>_<branch>/logs/` per target when run from the GUI's Batch tab).

**Reporting** (all ecosystems):
- `remediation-evidence.json` — the full machine-readable record: before/after JFrog scans, per-file write/validation status, verification outcome, diagnostic CSV contents.
- `task-completion-report.md` / `task-completion-report.xlsx` — the human-readable report; Overall Status (Success / Partial / Manual Update Required / Error) is driven by `remediation-evidence.json`'s verification outcome.
- `jfrog-audit.json` / `jfrog-audit-after.json` — the Xray scan before and after remediation.
- `phase2-results.json` — cached write/validate state for a `--phase2-results` replay.
- `logs/batch/batch-summary.log` — one appended entry per GUI batch run: aggregate statistics plus a per-repo status/time line (see GUI section above).

**npm:**
- `npm-available-versions.txt`, `npm-view-errors.csv`
- `direct-dependency-version-changes.csv`, `forced-overrides-changes.csv`, `forced-overrides-skipped.csv`
- `block-check-changes.csv`, `block-check-errors.csv`
- `npm-dependency-tree.json` / `-before.json` / `-after.json`

**Gradle:**
- `build-before.gradle`, `build-after.gradle`
- `gradle-dependency-tree.txt` / `-before.txt` / `-after.txt` / `-error.txt`
- `gradle-version-changes.csv`, `gradle-force-overrides.csv`, `gradle-fetch-errors.csv`, `gradle-skipped.csv`, `gradle-resolved-dependency-diff.csv`

**Python:**
- `python-dependency-tree.txt`
- `python-version-changes.csv`, `python-skipped.csv`

**Build validation / rollback** (all ecosystems, prefixed `build-validation-`):
- `build-validation-manual-updates.csv` — packages reverted with no safe fix found (full revert, or isolation disabled/exhausted).
- `build-validation-auto-fixes.csv` — packages successfully isolated/rolled back to restore a passing build.
- `build-validation-external-blockers.csv` / `build-validation-external-auto-fixes.csv` — build failures/fixes attributable to a blocked artifact outside this run's own changes (e.g. a transitive 403).
- `build-validation-preexisting-failures.csv` — test failures that already existed before remediation (updates were kept).
- `build-validation-debug.txt` — verbose trace of the proactive check / external-blocker-fix / isolation search for one run.
- `build-log-before.txt` / `build-log-after.txt` — only with `--capture-build-logs`.
- `verification-error.txt` — traceback from an unhandled exception during final verification, if one occurred.

## Development

    make test       # pytest
    make coverage    # pytest with coverage report
    make lint        # ruff check
    make format      # ruff format
    make clean       # remove .venv, caches, build artifacts

See `architecture.md` for the module/class structure and `flowchart.md` for the pipeline's decision logic (including how each ecosystem picks a target version).
