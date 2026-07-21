# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-21T12:51:50|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-consent-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/3/cwih-cnp-mgmt-consent-api|
|Dependency files|1|
|Changed packages|84|
|Skipped packages|0|
|Validation records|1|
|Taskboard CVEs tracked|7|
|Resolved dependency changes|0|
|Verification classification|Failed - tests did not pass|
|Test verification|failed|
|Original CVEs remaining|11|
|JFrog vulnerabilities before|55|
|JFrog vulnerabilities after|11|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|84|0|Written|Passed||Failed - tests did not pass|failed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle|1.5.21|1.5.38|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.2.10.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle|4.2.5.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle|1.5.21|1.5.38|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.10|1.17.0|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.10|3.5.13|Passed|True|
|build.gradle|gradle|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.2|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.14|3.3.16|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.10|4.5.13|Passed|True|
|build.gradle|gradle|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.2|2.5.3|Passed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle-force|1.5.21|1.5.38|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-base|gradle-force|4.2.10.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-core|gradle-force|2.21.2|2.22.1|Passed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-jcl|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-context|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-aop|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-beans|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-tx|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-oxm|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-context-support|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-messaging|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-test|gradle-force|6.2.17|6.2.19|Passed|True|
|build.gradle|gradle|io.netty:netty-common|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-buffer|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-unix-common|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns-native-macos|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns-classes-macos|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-classes-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-socks|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-observation|gradle-force|1.15.10|1.17.0|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-commons|gradle-force|1.15.10|1.17.0|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-jakarta9|gradle-force|1.15.10|1.17.0|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-registry-prometheus|gradle-force|1.15.10|1.17.0|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-webflux|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-autoconfigure|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-logging|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-json|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-reactor-netty|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-data-mongodb|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-actuator|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-actuator-autoconfigure|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-actuator|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-validation|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-configuration-processor|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-data-redis-reactive|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-hateoas|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-aop|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-test|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-test|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-test-autoconfigure|gradle-force|3.5.13|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-redis|gradle-force|3.5.10|3.5.13|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-keyvalue|gradle-force|3.5.10|3.5.13|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-spring-boot-starter-jaxws|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-spring-boot-autoconfigure|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-frontend-jaxws|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-bindings-soap|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-wsdl|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-databinding-jaxb|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-bindings-xml|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-frontend-simple|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-ws-addr|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-ws-policy|gradle-force|4.1.3|4.2.2|Passed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-features-metrics|gradle-force|4.1.3|4.2.2|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|dependency|blocked_version|forced_version|status|reason|source|
|---|---|---|---|---|---|
|com.fasterxml.jackson.core:jackson-databind|2.22.1|2.21.5|proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/logs/gradle-dependency-tree-before.txt|True|2175|2060|146283|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/logs/gradle-dependency-tree-after.txt|True|2175|2060|146283|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-consent-api/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
_No rows._

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2025-11226|Not found in dependency graph|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-27789|Not found in dependency graph|
|CVE-2025-48924|Not found in dependency graph|
|CVE-2025-55163|Not found in dependency graph|
|CVE-2025-58057|Not found in dependency graph|
