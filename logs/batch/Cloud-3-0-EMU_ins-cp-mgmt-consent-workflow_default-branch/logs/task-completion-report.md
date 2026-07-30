# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟡 Needs Review|
|Generated at|2026-07-29T08:24:57|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-consent-workflow.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/default-branch/ins-cp-mgmt-consent-workflow|
|Dependency files|1|
|Changed packages|22|
|Skipped packages|0|
|Validation records|0|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|56|
|Verification classification|Partial - build passed but 1 CVE record(s) remain|
|Test verification|passed|
|Original CVEs remaining|1|
|JFrog vulnerabilities before|72|
|JFrog vulnerabilities after|1|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟡 **REVIEW RECOMMENDED**

The build passed, but some findings remain (unresolved CVE records and/or alternate versions selected during validation).

Review:
- the post-update JFrog audit for remaining CVE records
- build-validation-external-auto-fixes.csv (if present)

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|22|0|Written|Passed||Partial - build passed but 1 CVE record(s) remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.32|1.6.1|Passed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.11|1.17.0|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.11|3.5.13|Passed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Passed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.15|3.3.16|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.54|10.1.57|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.54|10.1.57|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.11|4.5.13|Passed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webmvc|gradle-force|6.2.18|6.2.19|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
_No rows._

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/logs/gradle-dependency-tree-before.txt|True|1369|1262|83095|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/logs/gradle-dependency-tree-after.txt|True|1415|1308|87737|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-workflow_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java|1.10.1|1.11.1|changed|
|ch.qos.logback:logback-classic|1.5.32|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.32|1.6.1|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.21|2.22|changed|
|com.fasterxml.jackson.core:jackson-databind|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jsr310|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.21.2|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.21.2|2.22.1|changed|
|io.micrometer:context-propagation|1.1.4|1.2.1|changed|
|io.micrometer:micrometer-commons|1.15.11|1.17.0|changed|
|io.micrometer:micrometer-core|1.15.11|1.17.0|changed|
|io.micrometer:micrometer-jakarta9|1.15.11|1.17.0|changed|
|io.micrometer:micrometer-observation|1.15.11|1.17.0|changed|
|io.micrometer:micrometer-registry-prometheus|1.15.11|1.17.0|changed|
|io.netty:netty-buffer|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec|4.1.132.Final||removed|
|io.netty:netty-codec-base||4.2.16.Final|added|
|io.netty:netty-codec-compression||4.2.16.Final|added|
|io.netty:netty-codec-dns|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http2|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-socks|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-common|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-handler|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-handler-proxy|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-classes-macos|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-native-macos|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-transport|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-transport-classes-epoll|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-epoll|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-unix-common|4.1.132.Final|4.2.16.Final|changed|
|org.apache.tomcat.embed:tomcat-embed-core|10.1.54|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.54|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-websocket|10.1.54|10.1.57|changed|
|org.jspecify:jspecify||1.0.0|added|
|org.latencyutils:LatencyUtils|2.0.3||removed|
|org.springframework.data:spring-data-commons|3.5.11|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.5.11|4.5.13|changed|
|org.springframework.kafka:spring-kafka|3.3.15|3.3.16|changed|
|org.springframework:spring-aop|6.2.18|6.2.19|changed|
|org.springframework:spring-beans|6.2.18|6.2.19|changed|
|org.springframework:spring-context|6.2.18|6.2.19|changed|
|org.springframework:spring-context-support|6.2.18|6.2.19|changed|
|org.springframework:spring-core|6.2.18|6.2.19|changed|
|org.springframework:spring-expression|6.2.18|6.2.19|changed|
|org.springframework:spring-jcl|6.2.18|6.2.19|changed|
|org.springframework:spring-messaging|6.2.18|6.2.19|changed|
|org.springframework:spring-oxm|6.2.18|6.2.19|changed|
|org.springframework:spring-test|6.2.18|6.2.19|changed|
|org.springframework:spring-tx|6.2.18|6.2.19|changed|
|org.springframework:spring-web|6.2.18|6.2.19|changed|
|org.springframework:spring-webflux|6.2.18|6.2.19|changed|
|org.springframework:spring-webmvc|6.2.18|6.2.19|changed|
