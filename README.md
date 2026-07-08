# package_update

Automates dependency version updates driven by Azure DevOps (ADO) User Story tasks. It mines version requirements from task descriptions, resolves the best matching version from the registry, and rewrites `package.json` (npm) or `build.gradle` (Gradle) files accordingly.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)
  - [GUI (recommended)](#gui-recommended)
  - [Quick Update GUI](#quick-update-gui)
  - [CLI — Node / npm](#cli--node--npm)
  - [CLI — Gradle](#cli--gradle)
  - [CLI — Fetch ADO Tasks Only](#cli--fetch-ado-tasks-only)
- [How It Works](#how-it-works)
  - [Step 1: ADO Fetch](#step-1-ado-fetch)
  - [Step 2: Extract Version Requirements](#step-2-extract-version-requirements)
  - [Step 3: Resolve Best Version](#step-3-resolve-best-version)
  - [Step 4: Fetch Registry Versions](#step-4-fetch-registry-versions)
  - [Step 5: Apply Updates](#step-5-apply-updates)
  - [Step 6: CVE and Block Check](#step-6-cve-and-block-check)
  - [Step 7: Build Validation and Auto-Recovery](#step-7-build-validation-and-auto-recovery)
  - [Step 8: Write Output](#step-8-write-output)
- [Output Files](#output-files)
- [Configuration Reference](#configuration-reference)
  - [Auth Methods](#auth-methods)
  - [Selecting CSV Columns](#selecting-csv-columns)
  - [Claude Resolver Safety and Cache](#claude-resolver-safety-and-cache)
  - [Workers and Timeouts](#workers-and-timeouts)
  - [Validation Behavior](#validation-behavior)

---

## Prerequisites

- Python 3.13+
- Node.js + npm (for Node pipeline)
- Azure CLI (`az`) — install from go/shopping or self-service
- Claude CLI (`claude`) — install from go/shopping or self-service
- Access to the target ADO organization and project

Both `az` and `claude` must be on your PATH before running. The tool will exit with a clear error if either is missing.

For Gradle:
- Artifactory credentials with read access to the Maven repository

---

## Setup

```bash
make install
```

This creates a `.venv` and runs `pip install -e .` against `pyproject.toml`. Make tracks `pyproject.toml` as a dependency, so re-running after adding packages will re-install; it is a no-op otherwise.

| Target | Description |
|---|---|
| `make install` | Create `.venv` and install all dependencies |
| `make gui` | Launch the full GUI (creates venv if needed) |
| `make quick` | Launch the quick-update GUI (creates venv if needed) |
| `make clean` | Remove `.venv` and build artifacts |

If you need a pinned flat list for auditing or reproducibility, `requirements.txt` contains the same set with exact versions.

Optional environment variables (used as defaults in the GUI and Gradle CLI):

```bash
export ARTIFACTORY_SOURCE=https://your-org.jfrog.io/artifactory
export ARTIFACTORY_REPO=your-repo-virtual
export ARTIFACTORY_USERNAME=your-username
export ARTIFACTORY_PASSWORD=your-api-key

# Optional: JFrog Xray CVE checks
export JFROG_XRAY_HOST=https://your-org.jfrog.io
export JFROG_ACCESS_TOKEN=your-access-token
```

---

## Usage

### GUI (recommended)

```bash
make gui
```

The GUI runs both the Node and Gradle pipelines and provides a live log, a changes table, and a skipped-packages table. Parameters are saved to `~/.package_update_gui.json` and restored on next launch.

**Workflow:**

1. **ADO Connection** — choose auth method (Azure CLI or MSAL browser) and paste the ADO User Story URL. The org, project, and story ID are filled automatically.
2. **Project Directory** — enter or browse to the root of the project you want to update, then click **Scan for Dependency Files**. Check the files you want to process (`package.json`, `build.gradle`).
3. **Options** — adjust workers, CSV columns to scan, and log directory as needed.
4. **Advanced** — expand to configure npm registry, Artifactory credentials, or timeouts if your environment requires non-default settings.
5. Click **Analyze**. The log tab streams live output. When complete, review the **Changes** tab.
6. Click **Write Output** to apply the changes in-place (a `.bak` backup is created automatically).

### Quick Update GUI

A minimal two-field interface — just the project directory and ADO story URL. Uses Azure CLI auth, scans for supported dependency files, and updates all detected package.json and build.gradle files in place.

```bash
make quick
```

### CLI — Node / npm

Requires a pre-fetched ADO task CSV (see [Fetch ADO Tasks Only](#cli--fetch-ado-tasks-only)).

```bash
.venv/bin/python3 update_packages.py \
  --package-json /path/to/package.json \
  --csv logs/ado-task-descriptions.csv \
  --in-place
```

Common flags:

| Flag | Default | Description |
|---|---|---|
| `--package-json` | *(required)* | Path to `package.json` |
| `--csv` | *(required)* | ADO task CSV produced by `get_tasks.py` or `ado.py` |
| `--columns` | all | Comma-separated CSV columns to scan, e.g. `title,description` |
| `--in-place` | off | Overwrite `package.json`; creates a `.bak` backup |
| `--out` | `package.forced-overrides.json` | Output path when not using `--in-place` |
| `--log-dir` | `logs` | Directory for all log/CSV output files |
| `--workers` | `8` | Parallel npm worker threads |
| `--npm-timeout` | `90` | Per-call npm timeout (seconds) |
| `--registry` | *(uses `.npmrc`)* | npm registry URL |
| `--npm-cmd` | `npm` | npm executable |
| `--skip-block-check` | off | Skip Artifactory 403 checks and Xray candidate filtering |
| `--skip-build-validation` | off | Skip final project build validation after writing in-place |
| `--build-timeout` | `300` | Final build validation timeout in seconds |
| `--allow-ambiguous-highest-major` | off | Force the highest major when ADO mentions multiple incompatible versions |
| `--dry-run` | off | Run the full pipeline but do not write any output files |

### CLI — Gradle

```bash
.venv/bin/python3 update_gradle.py \
  --build-file /path/to/build.gradle \
  --csv logs/ado-task-descriptions.csv \
  --in-place
```

Reads Artifactory credentials from `ARTIFACTORY_SOURCE`, `ARTIFACTORY_REPO`, `ARTIFACTORY_USERNAME`, `ARTIFACTORY_PASSWORD` environment variables if not passed as flags.

| Flag | Default | Description |
|---|---|---|
| `--build-file` | `build.gradle` | Path to `build.gradle` |
| `--csv` | *(optional)* | ADO task CSV; without it all deps are updated to latest |
| `--in-place` | off | Overwrite in place; creates `.bak` |
| `--out` | `build.gradle.updated` | Output path |
| `--log-dir` | `logs` | Log directory |
| `--workers` | `8` | Parallel Artifactory fetch workers |
| `--timeout` | `30` | HTTP timeout per request (seconds) |
| `--skip-block-check` | off | Skip Artifactory 403 checks and Xray candidate filtering |
| `--skip-build-validation` | off | Skip final Gradle build validation after writing in-place |
| `--build-timeout` | `300` | Final build validation timeout in seconds |

### CLI — Fetch ADO Tasks Only

**Using Azure CLI auth** (requires `az login`):

```bash
.venv/bin/python3 get_tasks.py \
  --org https://dev.azure.com/your-org \
  --project "Your Project" \
  --story-id 12345 \
  --out logs/ado-task-descriptions.csv
```

**Using MSAL browser auth** (requires an Entra app registration):

```bash
.venv/bin/python3 ado.py \
  --org https://dev.azure.com/your-org \
  --project "Your Project" \
  --story-id 12345 \
  --client-id <your-app-client-id> \
  --out logs/ado-task-descriptions.csv
```

---

## How It Works

### Step 1: ADO Fetch

The tool authenticates with Azure DevOps using either:

- **Azure CLI** — reads the token cached by `az login` via `azure.identity.AzureCliCredential`. If the token is expired, it automatically runs `az login` and retries.
- **MSAL browser** — opens a browser window for interactive login using a registered Entra application.

Once authenticated, it:
1. Fetches the specified User Story and reads all child work item IDs from `System.LinkTypes.Hierarchy-Forward` relations.
2. Batch-fetches all child items (200 at a time) via the ADO Work Items Batch API.
3. Filters to items where `WorkItemType == "Task"` and strips HTML from descriptions.
4. Writes `logs/ado-task-descriptions.csv`.

### Step 2: Extract Version Requirements

For each dependency file, the tool scans every ADO task to find the packages and versions that need updating. It uses a two-stage approach: a fast CVE/GHSA database lookup for tasks whose titles contain a known advisory ID, followed by NLP for everything else.

#### CVE / GHSA Lookup (primary)

If a task title matches the pattern `CVE-YYYY-NNNNN` or `GHSA-XXXX-XXXX-XXXX` (e.g. `CVIT - my-app - Dev - GHSA-r4q5-vmmm-2653`), the tool resolves the affected packages and fixed versions directly from public vulnerability databases — no NLP required.

Resolution chain (tried in order, stops at first hit):

1. **OSV** (`api.osv.dev`) — the GitHub Advisory Database. GHSA entries always include ecosystem-tagged package names and SEMVER ranges. Most CVEs with a GitHub advisory are also mirrored here.
2. **GHSA alias** — if the CVE is in OSV but only carries a GIT range (no package metadata), the tool chases any GHSA aliases listed in the OSV response, which have full package data.
3. **NVD** (`services.nvd.nist.gov`) — used when OSV has no record of the CVE at all. Reads the `security-advisories@github.com`-sourced `affectedData` entries, which carry clean product names and `< X.Y.Z` version constraints.

For Maven/Gradle, NVD often provides product or CPE names instead of full Maven coordinates. The resolver matches those product names against the project's known `group:artifact` dependency universe before falling back to NLP. For example, an NVD product such as `netty-codec-http` can map to a known Maven artifact such as `io.netty:netty-codec-http`.

All advisory lookups across a run are deduplicated and fetched in parallel. If none of the above sources resolve a package name that exists in the project's dependency tree, the task falls through to NLP.

Packages identified via OSV/NVD are marked in the report's Changes sheet. Packages identified via NLP are marked with an asterisk (`*`) to indicate lower confidence.

#### NLP Extraction (fallback)

Tasks without a CVE/GHSA ID, or where the database lookup found no matching packages, are handled by NLP:

1. Collects all package names from `dependencies`, `devDependencies`, `peerDependencies`, `overrides`, and `resolutions` as the set of "known packages." Also resolves the full transitive tree from the lockfile so packages not declared directly (e.g. `tar`, `ip-address`) are visible.
2. Runs every task row through a regex pre-filter to extract semver strings and identify candidate package names. Two pattern types are used:
   - **Exact**: word-boundary match on the full package name (handles scoped packages like `@scope/pkg`).
   - **Fuzzy**: significant words from the package name (words ≥ 5 chars, excluding stopwords like "plugin", "loader", "utils"). Catches phrasings like "upgrade dompurify" where the full name isn't written.
3. Every row that contains at least one version number is sent to **Claude** (`claude` CLI, default model: `haiku`) in batches. The regex candidates are passed as hints. Claude determines which packages the task is actually describing and what constraint applies (`>=` = minimum required version; `>` = the mentioned version is bad, need strictly above it).
4. Claude's output is parsed and post-validated against the project dependency universe. By default, Claude may only select packages already known from the dependency file or resolved dependency tree; unlisted packages are ignored unless an explicit unlisted mode is enabled.
5. Claude CVE/task resolutions are cached so repeated runs do not keep re-running the same NLP fallback. Raw advisory facts can be cached by CVE ID, while Claude mappings are project-aware because the actionable package depends on the current project's known package set.

**For Gradle (`build.gradle`):**

Same two-stage flow applied to `group:artifact` dependency keys parsed from the Gradle file.

The `--claude-*` CLI flags control how Claude is invoked — model, effort level, timeout, parallelism, and batch size. Make sure the `claude` CLI is on your PATH before running.

### Step 3: Resolve Best Version

For each package with ADO-extracted versions:

- **`highest_ado_criteria_by_major()`** groups mentions by semver major and keeps the highest version seen per major. For example, if tasks mention `minimatch 3.0.4`, `minimatch 3.1.2`, and `minimatch 9.0.0`, the result is `{3: "3.1.2", 9: "9.0.0"}`.
- **`select_best_version()`** picks the best available version from the registry: the highest version that satisfies the ADO minimum for that major series, respecting the `>=` / `>` constraint.

### Step 4: Fetch Registry Versions

All queried packages are fetched in parallel using a thread pool (controlled by `--workers`).

- **Node**: runs `npm view <package> versions --json` for each package.
- **Gradle**: hits the Artifactory Maven metadata URL (`/maven-metadata.xml`) for each `group:artifact`.

Direct dependencies not covered by the ADO criteria are also pre-fetched so the tool can check whether updating a parent dependency would transitively resolve a CVE without needing an explicit `overrides` entry.

### Step 5: Apply Updates

**For Node:**

The tool works through each package in the resolved criteria and decides how to update it:

1. **Direct dependency**: if the package is in `dependencies` or `devDependencies`, update its version range in place (e.g., `"^2.0.0"` → `"^3.4.0"`). Preserves the existing range prefix (`^`, `~`, `>=`, etc.).

2. **Transitive dependency** (not a direct dep): the tool cannot update the version directly, so it uses npm's [overrides](https://docs.npmjs.com/cli/v10/configuring-npm/package-json#overrides) field to force a specific version across the entire dependency tree.

   - If multiple ADO majors are present (e.g., tasks mention both `minimatch 3.x` and `minimatch 9.x`), the tool reads `package-lock.json` to find which top-level direct dependencies pull in each major, then writes **nested overrides** (`overrides.<parent>.<package>`) to pin each major independently without forcing a global version that could break other consumers.
   - If only one major is required, it first checks whether updating a parent direct dependency to its latest same-major version would transitively satisfy the requirement (via `npm install --package-lock-only`). If so, it updates the parent instead of adding an override.
   - If neither approach applies, it writes a flat `overrides.<package>` entry.

3. **Skip conditions**: a package is skipped (with a recorded reason) if:
   - It uses a non-registry spec (git URL, `file:`, `link:`)
   - The current installed version already satisfies the ADO criteria
   - An existing override already satisfies the criteria
   - A parent dependency update would cover it
   - The version is ambiguous across majors with no resolvable dependents

Any stale `overrides` entries that would downgrade a direct dependency already at the required version are automatically removed.

**For Gradle:**

The tool works through each package in the resolved criteria:

1. **Direct dependency**: if the `group:artifact` is declared directly in `build.gradle`, update the version string in place.

2. **Transitive dependency** (not declared directly): the tool cannot update the version directly, so it uses Gradle's [`resolutionStrategy.force`](https://docs.gradle.org/current/dsl/org.gradle.api.artifacts.ResolutionStrategy.html) to pin a specific version across the entire dependency tree. Before adding a force, it checks whether updating a parent direct dependency to its latest same-major version would transitively pull in the required version (by running `gradle dependencies` in a temp directory). If so, it updates the parent instead.

3. **Skip conditions**: a package is skipped if:
   - The current resolved version already satisfies the ADO criteria
   - A parent dependency update would cover it

Force entries are written into a `configurations.all { resolutionStrategy { force '...' } }` block. If one already exists in the file, the `force` lines are inserted into it; otherwise a new block is prepended before the `dependencies` block.

### Step 6: CVE and Block Check

After applying updates, both Node and Gradle validate candidate artifacts before keeping them.

The check order is:

1. **JFrog Xray CVE filtering** — candidate component versions are batch-checked with Xray using `searchCvesByComponents`. Versions with CVEs are eliminated before block/access checks are attempted.
2. **Artifactory / registry block check** — remaining candidates are checked for accessibility, including HTTP 403 responses used by Artifactory to indicate blocked or quarantined artifacts.
3. **Forward then backward fallback** — the pipelines prefer safe same-major versions at or above the requested target. If no forward version is usable, they try lower same-major versions nearest-first. A backward version is only accepted if it has no Xray CVEs and is accessible.
4. **All-dependency Gradle coverage** — Gradle block checking is not limited to ADO-mentioned packages. It checks resolved dependencies across common configurations such as `runtimeClasspath`, `compileClasspath`, `testRuntimeClasspath`, and `testCompileClasspath`. Final build validation also remediates any additional 403-blocked artifacts found later.
For Node, safe fallback versions are written as direct dependency updates or npm `overrides`.

For Gradle, safe fallback versions are written as direct dependency changes when possible, including strict dependency blocks, and as `resolutionStrategy.force` entries when needed for transitive or classpath safety.

Skip with `--skip-block-check` only if your registry does not use 403-blocking and you do not want Xray CVE candidate filtering.

### Step 7: Build Validation and Auto-Recovery

When writing in-place, the pipelines validate the actual target project after dependency changes are applied.

**Node validation:**

1. Runs `npm install --no-audit --no-fund`.
2. Runs `npm run build` when `package.json` contains a `scripts.build` entry.
3. If validation fails, attempts targeted rollback of changed packages to isolate the breaking update.
**Gradle validation:**

1. Runs the detected Gradle command, such as `./gradlew build` or `gradle build`.
2. If the build fails because a Gradle artifact is blocked, parses all blocked `group:artifact:version` entries from the build output.
3. Attempts safe Xray-clean, accessible same-major fallback versions, including backward fallbacks.
4. Rewrites direct or strict dependency declarations when possible and adds force entries for transitive/classpath artifacts.
5. Re-runs the build before falling back to candidate rollback/manual marking.

If an automatic rollback or fallback fixes the build, the remaining valid updates are kept. If no safe automatic fix is found, the dependency file is restored from its pre-run snapshot and unresolved packages are marked for manual update.

Use `--skip-build-validation` only when you intentionally want to skip the final project build. If output is written to `--out` instead of in-place, final build validation is skipped because the target project was not modified.
### Step 8: Write Output

- **CLI**: writes the result immediately to `--out` or overwrites in-place with `--in-place`.
- **GUI**: the "Write Output" button writes in-place after the user has reviewed the Changes tab. A `.bak` backup is created the first time a file is written; subsequent writes do not overwrite the backup.

---

## Output Files

All written to `--log-dir` (default: `logs/`):

| File | Content |
|---|---|
| `ado-task-descriptions.csv` | All fetched ADO tasks: id, title, state, assigned_to, description, description_html, url |
| `ado-extracted-package-versions.txt` | Packages with ADO-mentioned versions and resolved criteria per major |
| `npm-available-versions.txt` | All registry versions fetched for each queried package |
| `npm-view-errors.csv` | Packages where `npm view` failed |
| `direct-dependency-version-changes.csv` | Direct dep updates: package, section, old_spec, new_spec, minimum_required, selected_version, path |
| `forced-overrides-changes.csv` | Override changes: package, old_override, new_override, minimum_required, removed_nested_override_paths |
| `forced-overrides-skipped.csv` | Packages skipped: package, reason, details |
| `block-check-changes.csv` | Versions changed due to Xray CVE filtering or blocked registry entries: package, blocked_version, unblocked_version |
| `block-check-errors.csv` | Packages that could not be unblocked: package, blocked_version, status, error |
| `gradle-version-changes.csv` | Gradle dep updates: dependency, config, old_version, new_version, ado_guided |
| `gradle-skipped.csv` | Gradle skipped: dependency, reason, current, target |
| `gradle-force-overrides.csv` | Gradle `resolutionStrategy.force` entries added: dependency, old_version, new_version, minimum_required |
| `gradle-fetch-errors.csv` | Artifactory fetch failures |
| `build-validation-auto-fixes.csv` | Packages automatically rolled back or remediated after final build validation failed |
| `build-validation-manual-updates.csv` | Packages that could not be safely fixed automatically and require manual update |
| `build-validation-external-auto-fixes.csv` | External Gradle artifacts remediated from final build output, such as blocked classpath dependencies |
| `app.log` | WARNING and ERROR messages from all pipeline runs; rotates daily, 7-day retention |
| `task-completion-report.xlsx` | Per-task Excel report with four sheets: Task Summary, Changes, Resolved, Skipped |

---

## Configuration Reference

### Auth Methods

| Method | When to use | Requirement |
|---|---|---|
| Azure CLI (`azcli`) | Personal machines; `az login` already done | `az` CLI installed |
| MSAL browser | CI or shared environments; Entra app registration | Client ID from an app registration with Azure DevOps API permissions |

### Selecting CSV Columns

The `--columns` / "CSV Columns" setting controls which columns of the ADO task CSV are scanned for package version mentions. Valid values are any combination of:

- `title` — task title only (fast, lower recall)
- `description` — plain-text description
- `description_html` — raw HTML description (highest recall; includes formatted version tables)

Default: `title,description,description_html`

### Claude Resolver Safety and Cache
Claude is a fallback resolver, not the primary mechanism. It is used when deterministic OSV/GHSA/NVD lookup cannot map a task to known packages.

Safety rules:

- Claude is not allowed to directly write dependency files.
- Claude is not allowed to choose final registry versions.
- Claude output is parsed and validated.
- By default, only packages from the known project dependency universe are accepted.
- Unlisted packages are ignored unless an explicit unlisted mode is enabled.

Caching:

- Raw advisory facts can be cached by CVE ID.
- Claude mappings are cached with project context because the same CVE may map to different actionable packages depending on the project's dependency tree.
- The practical cache key includes CVE/task identity, ecosystem, known-package-set hash, and resolver prompt/schema version.
### Workers and Timeouts

Worker threads are used for all parallel registry lookups. Higher values speed up the fetch phase for large dependency trees but may trigger rate limiting on some registries. The npm timeout applies per individual `npm view` call; the total time scales with the number of packages divided by the number of workers.

Recommended starting points:
- Internal Artifactory: 16–32 workers, 30 s timeout
- Public npmjs.org: 8–16 workers, 90 s timeout

### Validation Behavior

Build validation only runs after in-place writes. It is skipped for `--out` because the project dependency file was not modified.

- Node validation runs install and build when available.
- Gradle validation runs the project build and treats any final-build 403 artifact as another block-check event before rolling back candidates.
- If validation cannot find a safe automatic fix, the dependency file is restored and unresolved packages are logged for manual update.
