# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟢 Success|
|Generated at|2026-07-28T20:08:31|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-epms-cpms-preference-sync-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/default-branch/ins-cp-mgmt-epms-cpms-preference-sync-api|
|Dependency files|1|
|Changed packages|20|
|Skipped packages|0|
|Validation records|0|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|47|
|Verification classification|Success - build and tests passed; no CVEs remain|
|Test verification|passed|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|49|
|JFrog vulnerabilities after|0|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟢 **SUCCESS**

All remediation actions completed successfully.

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|20|0|Written|Passed||Success - build and tests passed; no CVEs remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle|2.22.0|2.22.1|Passed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle|1.5.19|1.6.1|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.22.0|2.22.1|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle|1.5.19|1.6.1|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.22.0|2.22.1|Passed|True|
|build.gradle|gradle|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.3|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.2.17|6.2.19|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
_No rows._

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/logs/gradle-dependency-tree-before.txt|True|1745|1659|118715|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/logs/gradle-dependency-tree-after.txt|True|2277|2162|151269|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-epms-cpms-preference-sync-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java|1.10.1|1.11.1|changed|
|ch.qos.logback:logback-classic|1.5.19|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.19|1.6.1|changed|
|com.fasterxml.jackson.core:jackson-core|2.22.0|2.22.1|changed|
|com.fasterxml.jackson.core:jackson-databind|2.22.0|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.22.0|2.22.1|changed|
|com.fasterxml.woodstox:woodstox-core|7.1.1|7.2.0|changed|
|io.netty:netty-buffer|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-codec|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-base|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-compression|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-dns|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http2|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-marshalling||4.2.16.Final|added|
|io.netty:netty-codec-protobuf||4.2.16.Final|added|
|io.netty:netty-codec-socks|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-common|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-handler|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-handler-proxy|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-resolver|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-classes-macos|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-native-macos|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-transport|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-transport-classes-epoll|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-epoll|4.1.135.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-unix-common|4.1.135.Final|4.2.16.Final|changed|
|org.apache.cxf:cxf-core|4.1.3|4.2.2|changed|
|org.apache.cxf:cxf-rt-transports-http|4.1.3|4.2.2|changed|
|org.apache.neethi:neethi|3.2.1|3.2.3|changed|
|org.apache.ws.xmlschema:xmlschema-core|2.3.1|2.3.2|changed|
|org.apiguardian:apiguardian-api||1.1.2|added|
|org.codehaus.woodstox:stax2-api|4.2.2|4.3.0|changed|
|org.springframework:spring-aop|6.2.17|6.2.19|changed|
|org.springframework:spring-beans|6.2.17|6.2.19|changed|
|org.springframework:spring-context|6.2.17|6.2.19|changed|
|org.springframework:spring-context-support|6.2.17|6.2.19|changed|
|org.springframework:spring-core|6.2.17|6.2.19|changed|
|org.springframework:spring-expression|6.2.17|6.2.19|changed|
|org.springframework:spring-jcl|6.2.17|6.2.19|changed|
|org.springframework:spring-messaging|6.2.17|6.2.19|changed|
|org.springframework:spring-oxm|6.2.17|6.2.19|changed|
|org.springframework:spring-test|6.2.17|6.2.19|changed|
|org.springframework:spring-tx|6.2.17|6.2.19|changed|
|org.springframework:spring-web|6.2.17|6.2.19|changed|
|org.springframework:spring-webflux|6.2.17|6.2.19|changed|
