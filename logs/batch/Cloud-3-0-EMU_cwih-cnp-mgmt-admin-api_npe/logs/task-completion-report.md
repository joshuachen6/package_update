# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟢 Success|
|Generated at|2026-07-22T11:06:37|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-admin-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/npe/cwih-cnp-mgmt-admin-api|
|Dependency files|1|
|Changed packages|41|
|Skipped packages|0|
|Validation records|0|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|48|
|Verification classification|Success - build and tests passed; no CVEs remain|
|Test verification|passed|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|64|
|JFrog vulnerabilities after|0|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/logs/jfrog-audit-after.json|

## Remediation Outcome

🟢 **SUCCESS**

All remediation actions completed successfully.

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|41|0|Written|Passed||Success - build and tests passed; no CVEs remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle|10.1.52|10.1.57|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|10.1.52|10.1.57|Passed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-el|gradle|10.1.52|10.1.57|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.32|1.5.38|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.11|3.5.13|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.15|3.3.16|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.11|4.5.13|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-el|gradle-force|10.1.52|10.1.57|Passed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-jcl|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-context|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-aop|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-beans|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-tx|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webmvc|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-messaging|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-test|gradle-force|6.2.18|6.2.19|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle-force|1.5.32|1.5.38|Passed|True|
|build.gradle|gradle|io.netty:netty-common|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-buffer|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-unix-common|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns-native-macos|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns-classes-macos|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-classes-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-socks|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle-force|2.21.2|2.22.1|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
_No rows._

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/logs/gradle-dependency-tree-before.txt|True|1332|1225|84793|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/logs/gradle-dependency-tree-after.txt|True|1356|1249|87209|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api_npe/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|ch.qos.logback:logback-classic|1.5.32|1.5.38|changed|
|ch.qos.logback:logback-core|1.5.32|1.5.38|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.21|2.22|changed|
|com.fasterxml.jackson.core:jackson-core|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.core:jackson-databind|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.dataformat:jackson-dataformat-yaml|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jsr310|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.21.2|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.21.2|2.22.1|changed|
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
|org.apache.tomcat.embed:tomcat-embed-core|10.1.52|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.52|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-websocket|10.1.52|10.1.57|changed|
|org.apache.tomcat:tomcat-annotations-api|10.1.54|10.1.57|changed|
|org.springframework.data:spring-data-commons|3.5.11|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.5.11|4.5.13|changed|
|org.springframework.kafka:spring-kafka|3.3.15|3.3.16|changed|
|org.springframework:spring-aop|6.2.18|6.2.19|changed|
|org.springframework:spring-beans|6.2.18|6.2.19|changed|
|org.springframework:spring-context|6.2.18|6.2.19|changed|
|org.springframework:spring-core|6.2.18|6.2.19|changed|
|org.springframework:spring-expression|6.2.18|6.2.19|changed|
|org.springframework:spring-jcl|6.2.18|6.2.19|changed|
|org.springframework:spring-messaging|6.2.18|6.2.19|changed|
|org.springframework:spring-test|6.2.18|6.2.19|changed|
|org.springframework:spring-tx|6.2.18|6.2.19|changed|
|org.springframework:spring-web|6.2.18|6.2.19|changed|
|org.springframework:spring-webflux|6.2.18|6.2.19|changed|
|org.springframework:spring-webmvc|6.2.18|6.2.19|changed|
