# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-28T09:00:32|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-consent-publish-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/default-branch/ins-cp-mgmt-consent-publish-api|
|Dependency files|1|
|Changed packages|29|
|Skipped packages|0|
|Validation records|30|
|Taskboard CVEs tracked|12|
|Resolved dependency changes|123|
|Verification classification|Failed - dependency updates could not be validated; manual review required|
|Test verification|not_run|
|Original CVEs remaining|69|
|JFrog vulnerabilities before|71|
|JFrog vulnerabilities after|71|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|29|0|Failed|Failed|Build validation failed. Failure isolation disabled.|Failed - dependency updates could not be validated; manual review required|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.1.128.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle|2.20.1|2.22.1|Failed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle|4.1.128.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle|4.1.128.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle|1.5.21|1.6.1|Failed|True|
|build.gradle|gradle|org.apache.kafka:kafka-clients|gradle|4.1.1|4.3.1|Failed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.11|6.2.19|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.20.1|2.22.1|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle|1.5.21|1.6.1|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.130.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.130.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.130.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.130.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.3|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.5.9|3.5.16|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.130.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-actuator|gradle-force|3.5.9|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.7|4.5.13|Failed|True|
|build.gradle|gradle|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.1|2.5.3|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.7|3.5.13|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.7|1.17.0|Failed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.11|3.3.16|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.11|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.11|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.11|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.2.11|6.2.19|Failed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.springframework.kafka:spring-kafka|gradle-force|3.3.11|3.3.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.kafka:kafka-clients|gradle|4.1.1|4.3.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-webflux|gradle-force|6.2.11|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-web|gradle-force|6.2.11|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-expression|gradle-force|6.2.11|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-core|gradle-force|6.2.11|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.1|2.5.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-mongodb|gradle-force|4.5.7|4.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-commons|gradle-force|3.5.7|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-actuator|gradle-force|3.5.9|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot|gradle-force|3.5.9|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport-native-epoll|gradle-force|4.1.130.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver-dns|gradle-force|4.1.130.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler-proxy|gradle-force|4.1.130.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http|gradle-force|4.1.130.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-dns|gradle-force|4.1.130.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-core|gradle-force|1.15.7|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-framework.version|gradle|6.2.11|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler|gradle|4.1.128.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http2|gradle|4.1.128.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec|gradle|4.1.128.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.fasterxml.jackson.core:jackson-databind|gradle|2.20.1|2.22.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.fasterxml.jackson.core:jackson-core|gradle|2.20.1|2.22.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|gradle|1.5.21|1.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-classic|gradle|1.5.21|1.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|||||proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/logs/gradle-dependency-tree-before.txt|True|2115|2000|143464|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/logs/gradle-dependency-tree-after.txt|True|653|627|44271|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-consent-publish-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java||1.10.2|added|
|ch.qos.logback:logback-classic|1.5.21|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.21|1.6.1|changed|
|com.fasterxml.jackson.core:jackson-core|2.20.1|2.22.1|changed|
|com.fasterxml.jackson.core:jackson-databind|2.20.1|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.19.4|2.21.4|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.19.4|2.21.4|changed|
|com.fasterxml.jackson:jackson-bom|2.20.1|2.22.1|changed|
|com.fasterxml.woodstox:woodstox-core|7.1.1|7.2.0|changed|
|com.fasterxml:classmate|1.7.1|1.7.3|changed|
|com.google.errorprone:error_prone_annotations|2.41.0||removed|
|com.google.guava:failureaccess|1.0.3||removed|
|com.google.guava:listenablefuture|9999.0-empty-to-avoid-conflict-with-guava||removed|
|com.google.j2objc:j2objc-annotations|3.1||removed|
|com.vaadin.external.google:android-json|0.0.20131108.vaadin1||removed|
|io.micrometer:context-propagation|1.1.3|1.2.1|changed|
|io.micrometer:micrometer-commons|1.15.7|1.17.0|changed|
|io.micrometer:micrometer-core|1.15.7|1.17.0|changed|
|io.micrometer:micrometer-jakarta9|1.15.7|1.17.0|changed|
|io.micrometer:micrometer-observation|1.15.7|1.17.0|changed|
|io.micrometer:micrometer-registry-prometheus|1.15.7|1.17.0|changed|
|io.micrometer:micrometer-tracing|1.5.7|1.5.12|changed|
|io.micrometer:micrometer-tracing-bridge-brave|1.5.7|1.5.12|changed|
|io.netty:netty-buffer|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-codec|4.1.128.Final|4.2.16.Final|changed|
|io.netty:netty-codec-base|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-compression|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-dns|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http2|4.1.128.Final|4.2.16.Final|changed|
|io.netty:netty-codec-marshalling||4.2.16.Final|added|
|io.netty:netty-codec-protobuf||4.2.16.Final|added|
|io.netty:netty-codec-socks|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-common|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-handler|4.1.128.Final|4.2.16.Final|changed|
|io.netty:netty-handler-proxy|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-resolver|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-classes-macos|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-native-macos|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-transport|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-transport-classes-epoll|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-epoll|4.1.130.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-unix-common|4.1.130.Final|4.2.16.Final|changed|
|io.projectreactor:reactor-core|3.7.14|3.7.19|changed|
|jakarta.xml.bind:jakarta.xml.bind-api|4.0.4|4.0.5|changed|
|jakarta.xml.ws:jakarta.xml.ws-api|4.0.2|4.0.3|changed|
|net.bytebuddy:byte-buddy|1.17.8||removed|
|net.bytebuddy:byte-buddy-agent|1.17.8||removed|
|org.apache.cxf:cxf-core|4.1.3|4.2.2|changed|
|org.apache.cxf:cxf-rt-transports-http|4.1.3|4.2.2|changed|
|org.apache.kafka:kafka-clients|4.1.1|4.3.1|changed|
|org.apache.kafka:kafka-raft|3.9.1|3.9.2|changed|
|org.apache.kafka:kafka-server-common|3.9.1|3.9.2|changed|
|org.apache.neethi:neethi|3.2.1|3.2.3|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.50|10.1.55|changed|
|org.apache.ws.xmlschema:xmlschema-core|2.3.1|2.3.2|changed|
|org.apiguardian:apiguardian-api|1.1.2||removed|
|org.awaitility:awaitility|4.2.2||removed|
|org.codehaus.woodstox:stax2-api|4.2.2|4.3.0|changed|
|org.glassfish.jaxb:jaxb-core|4.0.6|4.0.9|changed|
|org.glassfish.jaxb:jaxb-runtime|4.0.6|4.0.9|changed|
|org.glassfish.jaxb:txw2|4.0.6|4.0.9|changed|
|org.hamcrest:hamcrest|3.0||removed|
|org.jboss.logging:jboss-logging|3.6.1.Final|3.6.3.Final|changed|
|org.junit.jupiter:junit-jupiter|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-api|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-engine|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-params|5.12.2||removed|
|org.junit.platform:junit-platform-commons|1.12.2||removed|
|org.junit.platform:junit-platform-engine|1.12.2||removed|
|org.junit.platform:junit-platform-launcher|1.12.2||removed|
|org.junit:junit-bom|5.12.2||removed|
|org.latencyutils:LatencyUtils|2.0.3||removed|
|org.mockito:mockito-core|5.17.0||removed|
|org.mockito:mockito-junit-jupiter|5.17.0||removed|
|org.objenesis:objenesis|3.3||removed|
|org.opentest4j:opentest4j|1.3.0||removed|
|org.projectlombok:lombok|1.18.42|1.18.46|changed|
|org.skyscreamer:jsonassert|1.5.3||removed|
|org.slf4j:jul-to-slf4j|2.0.17|2.0.18|changed|
|org.slf4j:slf4j-api|2.0.17|2.0.18|changed|
|org.springframework.boot:spring-boot|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator-autoconfigure|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-autoconfigure|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-configuration-processor|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-actuator|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-aop|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-mongodb|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-redis-reactive|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-hateoas|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-json|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-logging|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-reactor-netty|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-test|3.5.9||removed|
|org.springframework.boot:spring-boot-starter-validation|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-webflux|3.5.9|3.5.16|changed|
|org.springframework.boot:spring-boot-test|3.5.9||removed|
|org.springframework.boot:spring-boot-test-autoconfigure|3.5.9||removed|
|org.springframework.data:spring-data-commons|3.5.7|3.5.13|changed|
|org.springframework.data:spring-data-keyvalue|3.5.7|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.5.7|4.5.13|changed|
|org.springframework.data:spring-data-redis|3.5.7|3.5.13|changed|
|org.springframework.hateoas:spring-hateoas|2.5.1|2.5.3|changed|
|org.springframework.kafka:spring-kafka|3.3.11|3.3.16|changed|
|org.springframework.security:spring-security-crypto|6.5.7|6.5.11|changed|
|org.springframework:spring-aop|6.2.11|6.2.19|changed|
|org.springframework:spring-beans|6.2.11|6.2.19|changed|
|org.springframework:spring-context|6.2.11|6.2.19|changed|
|org.springframework:spring-context-support|6.2.11|6.2.19|changed|
|org.springframework:spring-core|6.2.11|6.2.19|changed|
|org.springframework:spring-expression|6.2.11|6.2.19|changed|
|org.springframework:spring-jcl|6.2.11|6.2.19|changed|
|org.springframework:spring-messaging|6.2.11|6.2.19|changed|
|org.springframework:spring-oxm|6.2.11|6.2.19|changed|
|org.springframework:spring-test|6.2.11||removed|
|org.springframework:spring-tx|6.2.11|6.2.19|changed|
|org.springframework:spring-web|6.2.11|6.2.19|changed|
|org.springframework:spring-webflux|6.2.11|6.2.19|changed|
|org.webjars:webjars-locator-lite|1.1.2|1.1.3|changed|
|org.xmlunit:xmlunit-core|2.10.4||removed|

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2025-11226|Not found in dependency graph|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-22227|Not found in dependency graph|
|CVE-2025-22233|Not found in dependency graph|
|CVE-2025-41234|Not found in dependency graph|
|CVE-2025-41249|Not found in dependency graph|
|CVE-2025-48924|Not found in dependency graph|
|CVE-2025-55163|Not found in dependency graph|
|CVE-2025-58056|Not found in dependency graph|
|CVE-2025-58057|Not found in dependency graph|
|CVE-2025-7962|Not found in dependency graph|
