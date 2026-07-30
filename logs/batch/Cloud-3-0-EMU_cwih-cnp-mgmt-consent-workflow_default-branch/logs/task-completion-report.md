# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟡 Needs Review|
|Generated at|2026-07-29T07:47:27|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-consent-workflow.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/default-branch/cwih-cnp-mgmt-consent-workflow|
|Dependency files|1|
|Changed packages|26|
|Skipped packages|0|
|Validation records|1|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|82|
|Verification classification|Partial - build passed but 1 CVE record(s) remain|
|Test verification|passed|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|77|
|JFrog vulnerabilities after|1|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟡 **REVIEW RECOMMENDED**

The build passed, but some findings remain (unresolved CVE records and/or alternate versions selected during validation).

Review:
- the post-update JFrog audit for remaining CVE records
- build-validation-external-auto-fixes.csv (if present)

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|26|0|Written|Passed||Partial - build passed but 1 CVE record(s) remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.21|11.0.24|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle|1.5.25|1.6.1|Passed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle|1.5.25|1.6.1|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.10|1.17.0|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.53|10.1.57|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.10|3.5.13|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.10|4.5.13|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.14|3.3.16|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webmvc|gradle-force|6.2.17|6.2.19|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|dependency|blocked_version|forced_version|status|reason|source|
|---|---|---|---|---|---|
|com.fasterxml.jackson.core:jackson-databind||2.21.5|proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/logs/gradle-dependency-tree-before.txt|True|1297|1190|80197|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/logs/gradle-dependency-tree-after.txt|True|1335|1228|83017|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-workflow_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java|1.10.1|1.11.1|changed|
|ch.qos.logback:logback-classic|1.5.25|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.25|1.6.1|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.21|2.22|changed|
|com.fasterxml.jackson.core:jackson-core|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.core:jackson-databind|2.21.2|2.21.5|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jsr310|2.21.2|2.22.1|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.21.2|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.21.2|2.22.1|changed|
|io.micrometer:micrometer-commons|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-core|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-jakarta9|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-observation|1.15.10|1.17.0|changed|
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
|io.projectreactor.netty:reactor-netty-core|1.2.16|1.2.18|changed|
|io.projectreactor:reactor-core|3.7.17|3.7.19|changed|
|jakarta.xml.bind:jakarta.xml.bind-api|4.0.4|4.0.5|changed|
|org.apache.tomcat.embed:tomcat-embed-core|11.0.21|11.0.24|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.53|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-websocket|10.1.53|10.1.57|changed|
|org.apache.tomcat:tomcat-annotations-api|10.1.53|10.1.57|changed|
|org.jspecify:jspecify||1.0.0|added|
|org.latencyutils:LatencyUtils|2.0.3||removed|
|org.projectlombok:lombok|1.18.44|1.18.46|changed|
|org.slf4j:jul-to-slf4j|2.0.17|2.0.18|changed|
|org.slf4j:slf4j-api|2.0.17|2.0.18|changed|
|org.springframework.boot:spring-boot|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator-autoconfigure|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-autoconfigure|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-actuator|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-aop|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-mongodb|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-redis|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-json|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-logging|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-test|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-tomcat|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-validation|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-web|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-test|3.5.13|3.5.16|changed|
|org.springframework.boot:spring-boot-test-autoconfigure|3.5.13|3.5.16|changed|
|org.springframework.data:spring-data-commons|3.5.10|3.5.13|changed|
|org.springframework.data:spring-data-keyvalue|3.5.10|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.5.10|4.5.13|changed|
|org.springframework.data:spring-data-redis|3.5.10|3.5.13|changed|
|org.springframework.kafka:spring-kafka|3.3.14|3.3.16|changed|
|org.springframework.retry:spring-retry|2.0.12|2.0.13|changed|
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
|org.springframework:spring-webmvc|6.2.17|6.2.19|changed|
