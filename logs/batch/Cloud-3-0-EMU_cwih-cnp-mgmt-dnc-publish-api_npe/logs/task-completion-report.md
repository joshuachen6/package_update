# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-23T14:09:36|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-dnc-publish-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/npe/cwih-cnp-mgmt-dnc-publish-api|
|Dependency files|1|
|Changed packages|33|
|Skipped packages|4|
|Validation records|33|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|0|
|Verification classification|Failed - dependency updates could not be validated; manual review required|
|Test verification|not_run|
|Original CVEs remaining|94|
|JFrog vulnerabilities before|100|
|JFrog vulnerabilities after|100|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|33|4|Failed|Failed|Build validation failed. Failure isolation disabled.|Failed - dependency updates could not be validated; manual review required|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|com.github.jknack:handlebars|gradle|4.4.0|4.5.3|Failed|True|
|build.gradle|gradle|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|Failed|True|
|build.gradle|gradle|org.bouncycastle:bcprov-jdk18on|gradle|1.80|1.85|Failed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.18|11.0.24|Failed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle|3.3.6|3.3.16|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.10|1.17.0|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.25|1.6.0|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.2|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.10|3.5.13|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.10|4.5.13|Failed|True|
|build.gradle|gradle|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.2|2.5.3|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.3.6|5.4.3|Failed|True|
|build.gradle|gradle|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.3.6|5.4.3|Failed|True|
|build.gradle|gradle|org.codehaus.plexus:plexus-utils|gradle-force|3.5.1|3.6.1|Failed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle-force|4.1.3|4.2.2|Failed|True|

## Skipped / Resolved / Could Not Update
|file|ecosystem|package|current|target|status|reason|detail|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|io.netty:netty-codec|${nettyVersion}||Skipped|unparseable version||
|build.gradle|gradle|io.netty:netty-codec-http2|${nettyVersion}||Skipped|unparseable version||
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|${jacksonVersion}||Skipped|unparseable version||
|build.gradle|gradle|io.netty:netty-handler|${nettyVersion}||Skipped|unparseable version||

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.springframework:spring-webflux|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.2|2.5.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-mongodb|gradle-force|4.5.10|4.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-commons|gradle-force|3.5.10|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.codehaus.plexus:plexus-utils|gradle-force|3.5.1|3.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.3.6|5.4.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.3.6|5.4.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport-native-epoll|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver-dns|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler-proxy|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http2|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-dns|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec|gradle-force|4.1.127.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-core|gradle-force|1.15.10|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|gradle-force|1.5.25|1.6.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.kafka:spring-kafka|gradle|3.3.6|3.3.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.bouncycastle:bcprov-jdk18on|gradle|1.80|1.85|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.18|11.0.24|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.github.jknack:handlebars|gradle|4.4.0|4.5.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|||||proactive_force|blocked transitive detected in post-change dependency tree|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/logs/gradle-dependency-tree-before.txt|True|2432|2317|163329|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/logs/gradle-dependency-tree-after.txt|True|2432|2317|163329|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_npe/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
_No rows._
