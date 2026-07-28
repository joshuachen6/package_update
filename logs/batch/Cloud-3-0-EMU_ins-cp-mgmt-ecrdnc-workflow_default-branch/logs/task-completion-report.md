# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-28T09:14:14|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-ecrdnc-workflow.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/default-branch/ins-cp-mgmt-ecrdnc-workflow|
|Dependency files|1|
|Changed packages|12|
|Skipped packages|0|
|Validation records|13|
|Taskboard CVEs tracked|17|
|Resolved dependency changes|0|
|Verification classification|Failed - dependency updates could not be validated; manual review required|
|Test verification|not_run|
|Original CVEs remaining|44|
|JFrog vulnerabilities before|44|
|JFrog vulnerabilities after|44|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|12|0|Failed|Failed|Build validation failed. Failure isolation disabled.|Failed - dependency updates could not be validated; manual review required|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.springframework:spring-context|gradle|6.2.3|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-webmvc|gradle|6.2.10|6.2.19|Failed|True|
|build.gradle|gradle|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|Failed|True|
|build.gradle|gradle|org.springframework:spring-beans|gradle|6.2.3|6.2.19|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.13.14|1.17.0|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-actuator|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|Failed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.41|10.1.57|Failed|True|
|build.gradle|gradle|org.apache.commons:commons-lang3|gradle-force|3.14.0|3.20.0|Failed|True|
|build.gradle|gradle|org.assertj:assertj-core|gradle-force|3.25.3|3.27.7|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.41|10.1.57|Failed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.springframework.boot:spring-boot-starter-actuator|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.assertj:assertj-core|gradle-force|3.25.3|3.27.7|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.41|10.1.57|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.41|10.1.57|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.commons:commons-lang3|gradle-force|3.14.0|3.20.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-core|gradle-force|1.13.14|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-webmvc|gradle|6.2.10|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-context|gradle|6.2.3|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-beans|gradle|6.2.3|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|||||proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/logs/gradle-dependency-tree-before.txt|True|729|622|45503|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/logs/gradle-dependency-tree-after.txt|True|729|622|45507|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-ecrdnc-workflow_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
_No rows._

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2025-11226|Not found in dependency graph|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-22233|Still present after update|
|CVE-2025-41249|Not found in dependency graph|
|CVE-2025-48924|Still present after update|
|CVE-2025-48988|Still present after update|
|CVE-2025-48989|Still present after update|
|CVE-2025-49124|Still present after update|
|CVE-2025-49125|Still present after update|
|CVE-2025-52520|Still present after update|
|CVE-2025-53506|Not found in dependency graph|
|CVE-2025-55668|Still present after update|
|CVE-2025-55752|Still present after update|
|CVE-2025-55754|Still present after update|
|CVE-2025-58057|Still present after update|
|CVE-2025-61795|Still present after update|
