# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-28T09:12:04|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-evaluation-workflow.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/default-branch/cwih-cnp-mgmt-evaluation-workflow|
|Dependency files|1|
|Changed packages|26|
|Skipped packages|1|
|Validation records|26|
|Taskboard CVEs tracked|28|
|Resolved dependency changes|0|
|Verification classification|Failed - dependency updates could not be validated; manual review required|
|Test verification|not_run|
|Original CVEs remaining|59|
|JFrog vulnerabilities before|60|
|JFrog vulnerabilities after|60|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|26|1|Failed|Failed|Build validation failed. Failure isolation disabled.|Failed - dependency updates could not be validated; manual review required|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle|1.5.25|1.6.1|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle|2.19.4|2.22.1|Failed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle|3.3.5|3.3.16|Failed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.codehaus.plexus:plexus-utils|gradle|3.4.1|3.6.1|Failed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle|1.5.25|1.6.1|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-annotations|gradle|2.19.4|2.22|Failed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.11|1.17.0|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.11|4.5.13|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.11|3.5.13|Failed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.3.6|5.4.3|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.3.6|5.4.3|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|Failed|True|

## Skipped / Resolved / Could Not Update
|file|ecosystem|package|current|target|status|reason|detail|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|com.github.jknack:handlebars|[4.4.0]||Skipped|unparseable version||

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http2|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-webflux|gradle|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-mongodb|gradle-force|4.5.11|4.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-commons|gradle-force|3.5.11|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.kafka:spring-kafka|gradle|3.3.5|3.3.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.3.6|5.4.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.3.6|5.4.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-core|gradle-force|1.15.11|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.codehaus.plexus:plexus-utils|gradle|3.4.1|3.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.fasterxml.jackson.core:jackson-databind|gradle|2.19.4|2.22.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.fasterxml.jackson.core:jackson-annotations|gradle|2.19.4|2.22|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|gradle|1.5.25|1.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-classic|gradle|1.5.25|1.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/logs/gradle-dependency-tree-before.txt|True|1380|1300|92233|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/logs/gradle-dependency-tree-after.txt|True|1380|1300|92233|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-evaluation-workflow_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
_No rows._

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
|CVE-2025-3198|Not found in dependency graph|
|CVE-2025-41249|Not found in dependency graph|
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
|CVE-2025-55668|Not found in dependency graph|
|CVE-2025-55752|Not found in dependency graph|
|CVE-2025-55754|Not found in dependency graph|
|CVE-2025-61795|Not found in dependency graph|
|CVE-2025-6297|Not found in dependency graph|
|CVE-2025-7545|Not found in dependency graph|
|CVE-2025-8058|Not found in dependency graph|
|CVE-2025-8225|Not found in dependency graph|
|CVE-2025-9230|Not found in dependency graph|
