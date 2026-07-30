# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟡 Needs Review|
|Generated at|2026-07-29T08:03:49|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-admin-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/default-branch/ins-cp-mgmt-admin-api|
|Dependency files|1|
|Changed packages|6|
|Skipped packages|0|
|Validation records|1|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|16|
|Verification classification|Partial - build passed but 1 CVE record(s) remain|
|Test verification|passed|
|Original CVEs remaining|1|
|JFrog vulnerabilities before|29|
|JFrog vulnerabilities after|1|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟡 **REVIEW RECOMMENDED**

The build passed, but some findings remain (unresolved CVE records and/or alternate versions selected during validation).

Review:
- the post-update JFrog audit for remaining CVE records
- build-validation-external-auto-fixes.csv (if present)

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|6|0|Written|Passed||Partial - build passed but 1 CVE record(s) remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.32|1.6.1|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.15|3.3.16|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.54|10.1.57|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|dependency|blocked_version|forced_version|status|reason|source|
|---|---|---|---|---|---|
|io.netty:netty-codec|4.1.133.Final|4.1.136.Final|proactive_force|blocked transitive detected in post-change dependency tree|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/gradle-dependency-tree-before.txt|True|1101|994|71478|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/gradle-dependency-tree-after.txt|True|1101|994|71891|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-admin-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java|1.10.1|1.11.1|changed|
|ch.qos.logback:logback-classic|1.5.32|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.32|1.6.1|changed|
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
