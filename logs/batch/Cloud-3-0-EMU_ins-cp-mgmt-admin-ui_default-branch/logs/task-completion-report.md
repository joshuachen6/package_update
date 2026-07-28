# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟡 Needs Review|
|Generated at|2026-07-28T09:23:44|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-admin-ui.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/default-branch/ins-cp-mgmt-admin-ui|
|Dependency files|1|
|Changed packages|11|
|Skipped packages|1|
|Validation records|0|
|Taskboard CVEs tracked|13|
|Resolved dependency changes|0|
|Verification classification|Partial - build passed but 15 CVE record(s) remain|
|Test verification|passed|
|Original CVEs remaining|15|
|JFrog vulnerabilities before|32|
|JFrog vulnerabilities after|15|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟡 **REVIEW RECOMMENDED**

The build passed, but some findings remain (unresolved CVE records and/or alternate versions selected during validation).

Review:
- the post-update JFrog audit for remaining CVE records
- build-validation-external-auto-fixes.csv (if present)

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|package.json|node|11|1|Written|Passed||Partial - build passed but 15 CVE record(s) remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|package.json|node|dompurify|direct|3.4.0|3.4.3|Passed|True|
|package.json|node|next|direct|15.5.18|15.5.19|Passed|True|
|package.json|node|@babel/core|override||7.29.6|Passed|True|
|package.json|node|brace-expansion|override|5.0.6|5.0.7|Passed|True|
|package.json|node|fast-uri|override|3.1.2|3.1.3|Passed|True|
|package.json|node|fflate|override||0.8.3|Passed|True|
|package.json|node|form-data|override||4.0.6|Passed|True|
|package.json|node|immutable|override|5.1.6|5.1.7|Passed|True|
|package.json|node|js-yaml|override|4.1.1|4.2.0|Passed|True|
|package.json|node|postcss|override||8.4.32|Passed|True|
|package.json|node|ws|override|8.20.1|8.21.0|Passed|True|

## Skipped / Resolved / Could Not Update
|file|ecosystem|package|current|target|status|reason|detail|
|---|---|---|---|---|---|---|---|
|package.json|node|quill|2.0.3|2.0.3|Skipped|direct dependency already meets selected version|current=2.0.3, selected=2.0.3|

## Build Validation
_No rows._

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/logs/gradle-dependency-tree-before.txt|False|0|0|0|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/logs/gradle-dependency-tree-after.txt|False|0|0|0|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/logs/npm-dependency-tree-before.json|True|1|871|394978|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-ui_default-branch/logs/npm-dependency-tree-after.json|True|1|871|395019|

## Resolved Dependency Changes
_No rows._

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2025-27789|Not found in dependency graph|
|CVE-2025-30218|Not found in dependency graph|
|CVE-2025-4802|Not found in dependency graph|
|CVE-2025-48068|Not found in dependency graph|
|CVE-2025-55173|Not found in dependency graph|
|CVE-2025-57752|Not found in dependency graph|
|CVE-2025-57822|Not found in dependency graph|
|CVE-2025-58754|Not found in dependency graph|
|CVE-2025-64118|Not found in dependency graph|
|CVE-2025-64718|Not found in dependency graph|
|CVE-2025-64756|Not found in dependency graph|
|CVE-2025-8058|Not found in dependency graph|
|GHSA-5jpx-9hw9-2fx4|Not found in dependency graph|
