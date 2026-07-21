# Package Update

JFrog-driven dependency remediation for Node.js and Gradle projects.

The workflow is intentionally simple:

1. Scan dependency files
2. Generate dependency context:
   - npm lockfile data for Node.js projects.
   - Gradle dependency tree data for Gradle projects.
3. Run JFrog Xray CVE audit against resolved components.
4. Use vulnerable package names reported by JFrog as the remediation source of truth.
5. Update direct dependencies, overrides, Gradle declarations, or Gradle force rules as needed.
6. Validate the build and roll back on failure.

Legacy task parsing, public advisory database package lookup, and NLP package resolution have been removed. Package identity now comes from JFrog findings.

## Requirements

- Python 3.11+
- npm, when remediating Node.js projects
- Gradle or a project Gradle wrapper, when remediating Gradle projects
- JFrog Artifactory/Xray access

## Configuration

Set these environment variables or pass the equivalent CLI options:

    export ARTIFACTORY_SOURCE="https://your-jfrog.example.com"
    export ARTIFACTORY_REPO="ins-cp-mgmt-gradle-virtual"
    export ARTIFACTORY_USERNAME="..."
    export ARTIFACTORY_PASSWORD="..."

`ARTIFACTORY_SOURCE` is used as the JFrog base URL for Xray CVE audit calls and Gradle metadata lookup. `ARTIFACTORY_REPO` is the Maven repository used for Gradle version metadata.

## UI

Run the quick UI:

    make quick_update


Run the full UI:

    make gui
    

## CLI

Run against a project directory:
    python3 quick_update.py --project-dir /path/to/project

Target explicit files:

    python3 quick_update.py \
      --project-dir /path/to/project \
      --package-json /path/to/project/package.json \
      --build-file /path/to/project/build.gradle

Useful options:

    python3 quick_update.py \
      --project-dir /path/to/project \
      --artifactory-source "$ARTIFACTORY_SOURCE" \
      --artifactory-repo "$ARTIFACTORY_REPO" \
      --artifactory-username "$ARTIFACTORY_USERNAME" \      --artifactory-password "$ARTIFACTORY_PASSWORD" \
      --workers 8 \
      --npm-timeout 90 \
      --gradle-timeout 30

Skip build validation only when you explicitly want file rewrites without rollback protection:

    python3 quick_update.py --project-dir /path/to/project --skip-build-validation

## Node.js remediation

For Node.js projects, the pipeline:

- Loads or generates `package-lock.json`.
- Runs JFrog audit on resolved npm components.
- Uses JFrog vulnerable package names to build remediation criteria from the currently installed lockfile version.
- Queries available npm versions.- Updates direct dependencies or `overrides`.
- Runs block/CVE filtering unless `--skip-block-check` is used.
- Validates the project and rolls back on failure.

## Gradle remediation

For Gradle projects, the pipeline:

- Parses declared dependencies from `build.gradle`.
- Resolves dependency trees across common configurations.
- Runs JFrog audit on resolved Maven components.
- Uses JFrog vulnerable Maven coordinates as the remediation source of truth.
- Updates direct dependency declarations when possible.
- Updates direct parents for transitive dependencies when that resolves the vulnerable child.
- Adds `resolutionStrategy.force` entries when a direct update is not possible.- Validates the Gradle project and rolls back on failure.

## Logs

Logs are written under `<project-dir>/logs` by default.

Common outputs include:

- `jfrog-audit.json`
- `npm-available-versions.txt`
- `npm-view-errors.csv`
- `direct-dependency-version-changes.csv`
- `forced-overrides-changes.csv`
- `forced-overrides-skipped.csv`
- `block-check-changes.csv`
- `block-check-errors.csv`
- `gradle-dependency-tree.txt`
- `gradle-dependency-tree-error.txt`
- `gradle-fetch-errors.csv`
- `gradle-version-changes.csv`
- `gradle-force-overrides.csv`
- `gradle-skipped.csv`

## Notes

- JFrog findings are authoritative for package identity.
- Legacy task-based reports and task tagging have been removed.
