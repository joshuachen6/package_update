# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟢 Success|
|Generated at|2026-07-24T08:22:47|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-admin-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/default-branch/ins-cp-mgmt-admin-api|
|Dependency files|1|
|Changed packages|6|
|Skipped packages|0|
|Validation records|1|
|Taskboard CVEs tracked|32|
|Resolved dependency changes|16|
|Verification classification|Success - build and tests passed; no CVEs remain|
|Test verification|passed|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|28|
|JFrog vulnerabilities after|0|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟢 **SUCCESS**

All remediation actions completed successfully.

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|6|0|Written|Passed||Success - build and tests passed; no CVEs remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.32|1.6.0|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.15|3.3.16|Passed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.54|10.1.57|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.21.2|2.22.1|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|dependency|blocked_version|forced_version|status|reason|source|
|---|---|---|---|---|---|
|io.netty:netty-codec|4.1.133.Final|4.1.136.Final|proactive_force|blocked transitive detected in post-change dependency tree|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/gradle-dependency-tree-before.txt|True|1101|994|71482|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/gradle-dependency-tree-after.txt|True|1101|994|71890|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java|1.10.1|1.11.1|changed|
|ch.qos.logback:logback-classic|1.5.32|1.6.0|changed|
|ch.qos.logback:logback-core|1.5.32|1.6.0|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.21|2.22|changed|
|com.fasterxml.jackson.core:jackson-core|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.core:jackson-databind|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.dataformat:jackson-dataformat-yaml|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jsr310|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.21.2|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.21.2|2.22.1|changed|
|io.netty:netty-codec|4.1.133.Final|4.1.136.Final|changed|
|org.apache.tomcat.embed:tomcat-embed-core|10.1.54|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.54|10.1.57|changed|
|org.apache.tomcat:tomcat-annotations-api|10.1.54|10.1.57|changed|
|org.springframework.kafka:spring-kafka|3.3.15|3.3.16|changed|

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2025-11082|Not found in dependency graph|
|CVE-2025-11083|Not found in dependency graph|
|CVE-2025-11226|Not found in dependency graph|
|CVE-2025-1147|Not found in dependency graph|
|CVE-2025-1148|Not found in dependency graph|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-22233|Not found in dependency graph|
|CVE-2025-27789|Not found in dependency graph|
|CVE-2025-3198|Not found in dependency graph|
|CVE-2025-41249|Not found in dependency graph|
|CVE-2025-48924|Not found in dependency graph|
|CVE-2025-48988|Not found in dependency graph|
|CVE-2025-48989|Not found in dependency graph|
|CVE-2025-49124|Not found in dependency graph|
|CVE-2025-49125|Not found in dependency graph|
|CVE-2025-5244|Not found in dependency graph|
|CVE-2025-5245|Not found in dependency graph|
|CVE-2025-52520|Not found in dependency graph|
|CVE-2025-53057|Not found in dependency graph|
|CVE-2025-53066|Not found in dependency graph|
|CVE-2025-53506|Not found in dependency graph|
|CVE-2025-53864|Not found in dependency graph|
|CVE-2025-55668|Not found in dependency graph|
|CVE-2025-55752|Not found in dependency graph|
|CVE-2025-55754|Not found in dependency graph|
|CVE-2025-61795|Not found in dependency graph|
|CVE-2025-6297|Not found in dependency graph|
|CVE-2025-7545|Not found in dependency graph|
|CVE-2025-8058|Not found in dependency graph|
|CVE-2025-8225|Not found in dependency graph|
|CVE-2025-9230|Not found in dependency graph|
