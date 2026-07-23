# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-22T13:11:38|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-rule-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/default-branch/cwih-cnp-mgmt-rule-api|
|Dependency files|1|
|Changed packages|18|
|Skipped packages|0|
|Validation records|18|
|Taskboard CVEs tracked|5|
|Resolved dependency changes|0|
|Verification classification|Error - secondary verification scan incomplete|
|Test verification|not_run|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|23|
|JFrog vulnerabilities after|0|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|18|0|Failed|Failed|Build validation failed. Failure isolation disabled.|Error - secondary verification scan incomplete|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.18|11.0.24|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle|1.5.25|1.5.38|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle|1.5.25|1.5.38|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.52|10.1.57|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle-force|1.5.25|1.5.38|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-web|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-autoconfigure|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-logging|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-json|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-tomcat|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-aop|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-validation|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-test|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-test|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-test-autoconfigure|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-el|gradle-force|10.1.52|10.1.57|Failed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.springframework.boot:spring-boot-starter-validation|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-test-autoconfigure|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-test|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-web|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-tomcat|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-test|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-logging|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-json|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-aop|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-autoconfigure|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.52|10.1.57|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-el|gradle-force|10.1.52|10.1.57|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.18|11.0.24|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|gradle|1.5.25|1.5.38|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-classic|gradle|1.5.25|1.5.38|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|||||proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/logs/gradle-dependency-tree-before.txt|True|1345|1238|84628|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/logs/gradle-dependency-tree-after.txt|False|0|0|0|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-rule-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
_No rows._

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2022-26336|Not found in dependency graph|
|CVE-2025-11226|Not found in dependency graph|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-31672|Not found in dependency graph|
