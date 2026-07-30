# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-30T12:21:42|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-patient-mdm-master-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/default-branch/cwih-patient-mdm-master-api|
|Dependency files|1|
|Changed packages|8|
|Skipped packages|0|
|Validation records|8|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|0|
|Verification classification|Error - secondary verification scan incomplete|
|Test verification|not_run|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|50|
|JFrog vulnerabilities after|0|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|pom.xml|maven|8|0|Failed|Failed|Build validation failed. Failure isolation disabled.|Error - secondary verification scan incomplete|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|pom.xml|maven|ch.qos.logback:logback-core|maven-managed|1.5.25|0.2.5|Failed|True|
|pom.xml|maven|com.fasterxml.jackson.core:jackson-databind|maven|2.21.1|2.0.0-RC1|Failed|True|
|pom.xml|maven|org.apache.tomcat.embed:tomcat-embed-core|maven|11.0.18|7.0.0|Failed|True|
|pom.xml|maven|org.bouncycastle:bcprov-jdk18on|maven|1.79|1.71.1|Failed|True|
|pom.xml|maven|org.springframework:spring-core|maven-managed|6.2.11|1.0-rc1|Failed|True|
|pom.xml|maven|org.springframework:spring-web|maven|6.2.9|1.0-rc1|Failed|True|
|pom.xml|maven|org.springframework:spring-webmvc|maven|6.2.17|1.0-rc1|Failed|True|
|pom.xml|maven|org.springframework.boot:spring-boot-devtools|maven-managed||1.3.0.RELEASE|Failed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.springframework:spring-core|maven-managed|6.2.11|1.0-rc1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-webmvc|maven|6.2.17|1.0-rc1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-web|maven|6.2.9|1.0-rc1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-devtools|maven-managed||1.3.0.RELEASE|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|maven-managed|1.5.25|0.2.5|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.bouncycastle:bcprov-jdk18on|maven|1.79|1.71.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-core|maven|11.0.18|7.0.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.fasterxml.jackson.core:jackson-databind|maven|2.21.1|2.0.0-RC1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/logs/gradle-dependency-tree-before.txt|False|0|0|0|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/logs/gradle-dependency-tree-after.txt|False|0|0|0|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-patient-mdm-master-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
_No rows._
