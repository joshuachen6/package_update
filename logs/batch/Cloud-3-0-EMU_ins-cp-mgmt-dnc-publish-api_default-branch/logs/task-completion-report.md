# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-22T11:55:51|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-dnc-publish-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/default-branch/ins-cp-mgmt-dnc-publish-api|
|Dependency files|1|
|Changed packages|87|
|Skipped packages|1|
|Validation records|84|
|Taskboard CVEs tracked|19|
|Resolved dependency changes|230|
|Verification classification|Error - secondary verification scan incomplete|
|Test verification|not_run|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|96|
|JFrog vulnerabilities after|0|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🔴 **MANUAL UPDATE REQUIRED**

One or more dependency updates could not be completed automatically.

Review:
- build-validation-manual-updates.csv
- build-validation-auto-fixes.csv

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|87|1|Failed|Failed|Build validation failed. Failure isolation disabled.|Error - secondary verification scan incomplete|not_run|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|io.netty:netty-codec|gradle|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle|2.17.0|2.22.1|Failed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle|4.1.132.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.projectreactor.netty:reactor-netty-http|gradle|1.2.1|1.3.6|Failed|True|
|build.gradle|gradle|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|10.1.52|10.1.57|Failed|True|
|build.gradle|gradle|org.bouncycastle:bcprov-jdk18on|gradle|1.77|1.85|Failed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle|3.3.2|3.3.16|Failed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|io.projectreactor.netty:reactor-netty|gradle|1.2.1|1.3.6|Failed|True|
|build.gradle|gradle|io.projectreactor.netty:reactor-netty-core|gradle|1.2.1|1.3.6|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-annotations|gradle|2.17.0|2.22.1|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.0|4.2.2|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.neethi:neethi|gradle-force|3.2.0|3.2.2|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.13.14|1.17.0|Failed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.18|1.5.38|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.3.12|4.5.13|Failed|True|
|build.gradle|gradle|org.springframework.hateoas:spring-hateoas|gradle-force|2.3.4|2.5.3|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.3.12|3.5.13|Failed|True|
|build.gradle|gradle|org.springframework.security:spring-security-crypto|gradle-force|6.2.3|6.5.11|Failed|True|
|build.gradle|gradle|commons-beanutils:commons-beanutils|gradle-force|1.9.4|1.11.0|Failed|True|
|build.gradle|gradle|org.xmlunit:xmlunit-core|gradle-force|2.9.1|2.12.0|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.2.5|5.4.3|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.0|4.2.2|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.2.5|5.4.3|Failed|True|
|build.gradle|gradle|org.apache.commons:commons-lang3|gradle-force|3.14.0|3.20.0|Failed|True|
|build.gradle|gradle|org.assertj:assertj-core|gradle-force|3.25.3|3.27.7|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.eclipse.jgit:org.eclipse.jgit|gradle-force|6.6.1.202309021850-r|6.10.1.202505221210-r|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-annotations|gradle-force|2.17.0|2.22.1|Failed|True|
|build.gradle|gradle|io.projectreactor.netty:reactor-netty|gradle-force|1.2.1|1.3.6|Failed|True|
|build.gradle|gradle|io.projectreactor.netty:reactor-netty-core|gradle-force|1.2.1|1.3.6|Failed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-jcl|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-context|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-aop|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-beans|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-messaging|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-tx|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-oxm|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-context-support|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-test|gradle-force|6.2.0|6.2.19|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-base|gradle-force|4.2.5.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-observation|gradle-force|1.13.14|1.17.0|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-commons|gradle-force|1.13.14|1.17.0|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-jakarta9|gradle-force|1.13.14|1.17.0|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-registry-prometheus|gradle-force|1.13.14|1.17.0|Failed|True|
|build.gradle|gradle|io.netty:netty-common|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-buffer|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-transport|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-native-unix-common|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-socks|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns-native-macos|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns-classes-macos|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-classes-epoll|gradle-force|4.1.121.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-classic|gradle-force|1.5.18|1.5.38|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-redis|gradle-force|3.3.12|3.5.13|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-keyvalue|gradle-force|3.3.12|3.5.13|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle-force|4.1.0|4.2.2|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-autoconfigure|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-logging|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-actuator-autoconfigure|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-actuator|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-data-mongodb|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-webflux|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-json|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-reactor-netty|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-configuration-processor|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-data-redis-reactive|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-hateoas|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-aop|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-test|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-test|gradle-force|3.3.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-test-autoconfigure|gradle-force|3.3.12|3.5.16|Failed|True|

## Skipped / Resolved / Could Not Update
|file|ecosystem|package|current|target|status|reason|detail|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|com.github.jknack:handlebars|[4.4.0]||Skipped|unparseable version||

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|com.fasterxml.jackson.core:jackson-databind|gradle|2.17.0|2.22.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.fasterxml.jackson.core:jackson-annotations|gradle|2.17.0|2.22.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-configuration-processor|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.xmlunit:xmlunit-core|gradle-force|2.9.1|2.12.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-web|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-tx|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-test|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-oxm|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-messaging|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-jcl|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-expression|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-core|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-context-support|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-context|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-beans|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-aop|gradle-force|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.security:spring-security-crypto|gradle-force|6.2.3|6.5.11|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.hateoas:spring-hateoas|gradle-force|2.3.4|2.5.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-redis|gradle-force|3.3.12|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-mongodb|gradle-force|4.3.12|4.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-keyvalue|gradle-force|3.3.12|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-commons|gradle-force|3.3.12|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-test-autoconfigure|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-test|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-webflux|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-test|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-reactor-netty|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-logging|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-json|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-hateoas|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-data-redis-reactive|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-data-mongodb|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter-aop|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-starter|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-autoconfigure|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-actuator-autoconfigure|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot-actuator|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot|gradle-force|3.3.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.eclipse.jgit:org.eclipse.jgit|gradle-force|6.6.1.202309021850-r|6.10.1.202505221210-r|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.assertj:assertj-core|gradle-force|3.25.3|3.27.7|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.neethi:neethi|gradle-force|3.2.0|3.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.2.5|5.4.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.2.5|5.4.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-core|gradle-force|4.1.0|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.commons:commons-lang3|gradle-force|3.14.0|3.20.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport-native-unix-common|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport-native-epoll|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport-classes-epoll|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-transport|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver-dns-native-macos|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver-dns-classes-macos|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver-dns|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-resolver|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler-proxy|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-common|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-socks|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-dns|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-base|gradle-force|4.2.5.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-buffer|gradle-force|4.1.121.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-registry-prometheus|gradle-force|1.13.14|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-observation|gradle-force|1.13.14|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-jakarta9|gradle-force|1.13.14|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-core|gradle-force|1.13.14|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.micrometer:micrometer-commons|gradle-force|1.13.14|1.17.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|commons-beanutils:commons-beanutils|gradle-force|1.9.4|1.11.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|gradle-force|1.5.18|1.5.38|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-classic|gradle-force|1.5.18|1.5.38|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-webflux|gradle|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-framework.version|gradle|6.2.0|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.kafka:spring-kafka|gradle|3.3.2|3.3.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.bouncycastle:bcprov-jdk18on|gradle|1.77|1.85|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-core|gradle|10.1.52|10.1.57|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.0|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.projectreactor.netty:reactor-netty-http|gradle|1.2.1|1.3.6|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.projectreactor.netty:reactor-netty-core|gradle|1.2.1|1.3.6|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.projectreactor.netty:reactor-netty|gradle|1.2.1|1.3.6|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-handler|gradle|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http2|gradle|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec-http|gradle|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|io.netty:netty-codec|gradle|4.1.132.Final|4.2.16.Final|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|||||proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/logs/gradle-dependency-tree-before.txt|True|2337|2222|156690|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/logs/gradle-dependency-tree-after.txt|True|619|593|41163|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-dnc-publish-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java||1.10.2|added|
|ch.qos.logback:logback-classic|1.5.18|1.5.38|changed|
|ch.qos.logback:logback-core|1.5.18|1.5.38|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.17.0||removed|
|com.fasterxml.jackson.core:jackson-databind|2.17.0|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.17.3|2.22.1|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.17.3|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.21.1|2.22.1|changed|
|com.fasterxml.woodstox:woodstox-core|7.1.0|7.2.0|changed|
|com.fasterxml:classmate|1.7.0|1.7.3|changed|
|com.github.jknack:handlebars|4.4.0||removed|
|com.github.luben:zstd-jni|1.5.6-6|1.5.6-10|changed|
|com.github.tomakehurst:wiremock-jre8-standalone|2.35.1||removed|
|com.google.errorprone:error_prone_annotations|2.26.1||removed|
|com.google.guava:failureaccess|1.0.2||removed|
|com.google.guava:guava|33.1.0-jre||removed|
|com.google.guava:listenablefuture|9999.0-empty-to-avoid-conflict-with-guava||removed|
|com.google.j2objc:j2objc-annotations|3.0.0||removed|
|com.googlecode.javaewah:JavaEWAH|1.2.3||removed|
|com.ibm.icu:icu4j|72.1||removed|
|com.jcraft:jsch|0.1.55||removed|
|com.jcraft:jsch.agentproxy.core|0.0.9||removed|
|com.jcraft:jsch.agentproxy.jsch|0.0.9||removed|
|com.jcraft:jsch.agentproxy.sshagent|0.0.9||removed|
|com.jcraft:jsch.agentproxy.usocket-jna|0.0.9||removed|
|com.jcraft:jzlib|1.1.3||removed|
|com.rackspace.eclipse.webtools.sourceediting:org.eclipse.wst.xml.xpath2.processor|2.1.100||removed|
|com.toomuchcoding.jsonassert:jsonassert|0.8.0||removed|
|com.vaadin.external.google:android-json|0.0.20131108.vaadin1||removed|
|commons-beanutils:commons-beanutils|1.9.4||removed|
|commons-codec:commons-codec|1.16.1|1.18.0|changed|
|commons-collections:commons-collections|3.2.2||removed|
|commons-logging:commons-logging|1.2||removed|
|dk.brics:automaton|1.12-4||removed|
|io.lettuce:lettuce-core|6.3.2.RELEASE|6.6.0.RELEASE|changed|
|io.micrometer:context-propagation|1.1.3|1.2.1|changed|
|io.micrometer:micrometer-commons|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-core|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-jakarta9|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-observation|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-registry-prometheus|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-tracing|1.3.12|1.5.12|changed|
|io.micrometer:micrometer-tracing-bridge-brave|1.3.12|1.5.12|changed|
|io.netty.incubator:netty-incubator-codec-classes-quic|0.0.68.Final||removed|
|io.netty.incubator:netty-incubator-codec-native-quic|0.0.68.Final||removed|
|io.netty:netty-buffer|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-codec|4.1.132.Final||removed|
|io.netty:netty-codec-base|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-classes-quic||4.2.16.Final|added|
|io.netty:netty-codec-compression|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-dns|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http2|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http3||4.2.16.Final|added|
|io.netty:netty-codec-marshalling||4.2.16.Final|added|
|io.netty:netty-codec-native-quic||4.2.16.Final|added|
|io.netty:netty-codec-protobuf||4.2.16.Final|added|
|io.netty:netty-codec-socks|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-common|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-handler|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-handler-proxy|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-resolver|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-classes-macos|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-native-macos|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-transport|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-transport-classes-epoll|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-epoll|4.1.121.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-unix-common|4.1.121.Final|4.2.16.Final|changed|
|io.projectreactor.netty.incubator:reactor-netty-incubator-quic|0.2.1||removed|
|io.projectreactor.netty:reactor-netty|1.2.1|1.3.6|changed|
|io.projectreactor.netty:reactor-netty-core|1.2.1|1.3.6|changed|
|io.projectreactor.netty:reactor-netty-http|1.2.1|1.3.6|changed|
|io.projectreactor:reactor-core|3.6.17|3.7.19|changed|
|io.projectreactor:reactor-test|3.4.3||removed|
|io.prometheus:prometheus-metrics-config|1.2.1|1.3.10|changed|
|io.prometheus:prometheus-metrics-core|1.2.1|1.3.10|changed|
|io.prometheus:prometheus-metrics-exposition-formats|1.2.1|1.3.10|changed|
|io.prometheus:prometheus-metrics-exposition-textformats||1.3.10|added|
|io.prometheus:prometheus-metrics-model|1.2.1|1.3.10|changed|
|io.prometheus:prometheus-metrics-shaded-protobuf|1.2.1||removed|
|io.prometheus:prometheus-metrics-tracer-common|1.2.1|1.3.10|changed|
|io.zipkin.aws:brave-propagation-aws|1.2.5|1.3.0|changed|
|io.zipkin.brave:brave|6.0.3|6.1.0|changed|
|io.zipkin.brave:brave-context-slf4j|6.0.3|6.1.0|changed|
|io.zipkin.brave:brave-instrumentation-http|6.0.3|6.1.0|changed|
|jakarta.activation:jakarta.activation-api|2.1.3|2.1.4|changed|
|jakarta.mail:jakarta.mail-api|2.1.3|2.1.5|changed|
|jakarta.xml.bind:jakarta.xml.bind-api|4.0.2|4.0.5|changed|
|jakarta.xml.ws:jakarta.xml.ws-api|4.0.2|4.0.3|changed|
|javax.annotation:jsr250-api|1.0||removed|
|javax.enterprise:cdi-api|1.0||removed|
|net.bytebuddy:byte-buddy|1.14.19||removed|
|net.bytebuddy:byte-buddy-agent|1.14.19||removed|
|net.java.dev.jna:jna-platform|5.13.0||removed|
|net.javacrumbs.json-unit:json-unit-assertj|2.38.0||removed|
|net.javacrumbs.json-unit:json-unit-core|2.38.0||removed|
|net.javacrumbs.json-unit:json-unit-json-path|2.38.0||removed|
|org.apache.commons:commons-lang3|3.14.0|3.17.0|changed|
|org.apache.cxf:cxf-core|4.1.0|4.2.2|changed|
|org.apache.cxf:cxf-rt-transports-http|4.1.0|4.2.2|changed|
|org.apache.groovy:groovy|4.0.26||removed|
|org.apache.groovy:groovy-bom|4.0.26||removed|
|org.apache.groovy:groovy-json|4.0.26||removed|
|org.apache.groovy:groovy-nio|4.0.26||removed|
|org.apache.groovy:groovy-xml|4.0.26||removed|
|org.apache.httpcomponents.client5:httpclient5|5.3.1||removed|
|org.apache.httpcomponents.core5:httpcore5|5.2.5||removed|
|org.apache.httpcomponents.core5:httpcore5-h2|5.2.5||removed|
|org.apache.httpcomponents:httpclient|4.5.14||removed|
|org.apache.httpcomponents:httpcore|4.4.16||removed|
|org.apache.kafka:kafka-clients|4.0.0|4.3.1|changed|
|org.apache.logging.log4j:log4j-api|2.23.1|2.24.3|changed|
|org.apache.logging.log4j:log4j-to-slf4j|2.23.1|2.24.3|changed|
|org.apache.maven.resolver:maven-resolver-api|1.9.18||removed|
|org.apache.maven.resolver:maven-resolver-connector-basic|1.9.16||removed|
|org.apache.maven.resolver:maven-resolver-impl|1.9.16||removed|
|org.apache.maven.resolver:maven-resolver-named-locks|1.9.16||removed|
|org.apache.maven.resolver:maven-resolver-spi|1.9.16||removed|
|org.apache.maven.resolver:maven-resolver-transport-http|1.9.16||removed|
|org.apache.maven.resolver:maven-resolver-util|1.9.16||removed|
|org.apache.maven:maven-artifact|3.9.5||removed|
|org.apache.maven:maven-builder-support|3.9.5||removed|
|org.apache.maven:maven-model|3.9.5||removed|
|org.apache.maven:maven-model-builder|3.9.5||removed|
|org.apache.maven:maven-repository-metadata|3.9.5||removed|
|org.apache.maven:maven-resolver-provider|3.9.5||removed|
|org.apache.neethi:neethi|3.2.0|3.2.2|changed|
|org.apache.tomcat.embed:tomcat-embed-core|10.1.52|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.41|10.1.55|changed|
|org.apache.tomcat:tomcat-annotations-api|10.1.41|10.1.55|changed|
|org.apache.ws.xmlschema:xmlschema-core|2.3.1|2.3.2|changed|
|org.apiguardian:apiguardian-api|1.1.2||removed|
|org.aspectj:aspectjweaver|1.9.24|1.9.25.1|changed|
|org.assertj:assertj-core|3.25.3||removed|
|org.awaitility:awaitility|4.2.2||removed|
|org.bouncycastle:bcprov-jdk18on|1.77|1.85|changed|
|org.checkerframework:checker-qual|3.42.0||removed|
|org.codehaus.plexus:plexus-classworlds|2.5.2||removed|
|org.codehaus.plexus:plexus-component-annotations|1.5.5||removed|
|org.codehaus.plexus:plexus-interpolation|1.26||removed|
|org.codehaus.plexus:plexus-utils|4.0.3||removed|
|org.codehaus.woodstox:stax2-api|4.2.2|4.3.0|changed|
|org.eclipse.angus:angus-activation|2.0.2|2.0.3|changed|
|org.eclipse.jgit:org.eclipse.jgit|6.6.1.202309021850-r||removed|
|org.eclipse.jgit:org.eclipse.jgit.ssh.jsch|6.7.0.202309050840-r||removed|
|org.eclipse.sisu:org.eclipse.sisu.inject|0.3.5||removed|
|org.eclipse.sisu:org.eclipse.sisu.plexus|0.3.0||removed|
|org.glassfish.jaxb:jaxb-core|4.0.5|4.0.9|changed|
|org.glassfish.jaxb:jaxb-runtime|4.0.5|4.0.9|changed|
|org.glassfish.jaxb:txw2|4.0.5|4.0.9|changed|
|org.hamcrest:hamcrest|2.2||removed|
|org.hamcrest:hamcrest-core|2.2||removed|
|org.hibernate.validator:hibernate-validator|8.0.2.Final|8.0.3.Final|changed|
|org.jboss.logging:jboss-logging|3.5.3.Final|3.6.3.Final|changed|
|org.jspecify:jspecify||1.0.0|added|
|org.junit.jupiter:junit-jupiter|5.10.5||removed|
|org.junit.jupiter:junit-jupiter-api|5.10.5||removed|
|org.junit.jupiter:junit-jupiter-engine|5.10.5||removed|
|org.junit.jupiter:junit-jupiter-params|5.10.5||removed|
|org.junit.platform:junit-platform-commons|1.10.5||removed|
|org.junit.platform:junit-platform-engine|1.10.5||removed|
|org.junit.platform:junit-platform-launcher|1.10.5||removed|
|org.junit:junit-bom|5.10.5||removed|
|org.latencyutils:LatencyUtils|2.0.3||removed|
|org.lz4:lz4-java|1.8.0||removed|
|org.mockito:mockito-core|5.11.0||removed|
|org.mockito:mockito-junit-jupiter|5.11.0||removed|
|org.mongodb:bson|5.0.1|5.5.2|changed|
|org.mongodb:bson-record-codec|5.0.1|5.5.2|changed|
|org.mongodb:mongodb-driver-core|5.0.1|5.5.2|changed|
|org.mongodb:mongodb-driver-sync|5.0.1|5.5.2|changed|
|org.objenesis:objenesis|3.3||removed|
|org.opentest4j:opentest4j|1.3.0||removed|
|org.projectlombok:lombok|1.18.38|1.18.46|changed|
|org.skyscreamer:jsonassert|1.5.3||removed|
|org.slf4j:jul-to-slf4j|2.0.17|2.0.18|changed|
|org.slf4j:slf4j-api|2.0.17|2.0.18|changed|
|org.sonatype.sisu:sisu-guice|3.2.5||removed|
|org.sonatype.sisu:sisu-inject-bean|2.6.0||removed|
|org.sonatype.sisu:sisu-inject-plexus|2.6.0||removed|
|org.springframework.boot:spring-boot|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator-autoconfigure|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-autoconfigure|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-configuration-processor|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-aop|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-mongodb|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-redis-reactive|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-hateoas|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-json|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-logging|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-reactor-netty|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-test|3.3.12||removed|
|org.springframework.boot:spring-boot-starter-webflux|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-test|3.3.12||removed|
|org.springframework.boot:spring-boot-test-autoconfigure|3.3.12||removed|
|org.springframework.cloud:spring-cloud-contract-converters|4.1.4||removed|
|org.springframework.cloud:spring-cloud-contract-spec|4.1.4||removed|
|org.springframework.cloud:spring-cloud-contract-spec-groovy|4.1.4||removed|
|org.springframework.cloud:spring-cloud-contract-spec-java|4.1.4||removed|
|org.springframework.cloud:spring-cloud-contract-stub-runner|4.1.4||removed|
|org.springframework.cloud:spring-cloud-contract-verifier|4.1.4||removed|
|org.springframework.cloud:spring-cloud-contract-wiremock|4.1.4||removed|
|org.springframework.cloud:spring-cloud-starter-contract-stub-runner|4.1.1||removed|
|org.springframework.cloud:spring-cloud-test-support|4.1.4||removed|
|org.springframework.data:spring-data-commons|3.3.12|3.5.13|changed|
|org.springframework.data:spring-data-keyvalue|3.3.12|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.3.12|4.5.13|changed|
|org.springframework.data:spring-data-redis|3.3.12|3.5.13|changed|
|org.springframework.hateoas:spring-hateoas|2.3.4|2.5.3|changed|
|org.springframework.kafka:spring-kafka|3.3.2|3.3.16|changed|
|org.springframework.retry:spring-retry|2.0.12|2.0.13|changed|
|org.springframework:spring-aop|6.2.0|6.2.19|changed|
|org.springframework:spring-beans|6.2.0|6.2.19|changed|
|org.springframework:spring-context|6.2.0|6.2.19|changed|
|org.springframework:spring-context-support|6.2.0|6.2.19|changed|
|org.springframework:spring-core|6.2.0|6.2.19|changed|
|org.springframework:spring-expression|6.2.0|6.2.19|changed|
|org.springframework:spring-jcl|6.2.0|6.2.19|changed|
|org.springframework:spring-messaging|6.2.0|6.2.19|changed|
|org.springframework:spring-oxm|6.2.0|6.2.19|changed|
|org.springframework:spring-test|6.2.0||removed|
|org.springframework:spring-tx|6.2.0|6.2.19|changed|
|org.springframework:spring-web|6.2.0|6.2.19|changed|
|org.springframework:spring-webflux|6.2.17|6.2.19|changed|
|org.xerial.snappy:snappy-java|1.1.10.5|1.1.10.7|changed|
|org.xmlunit:xmlunit-core|2.9.1||removed|
|redis.clients.authentication:redis-authx-core||0.1.1-beta2|added|

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2024-29857|Verification incomplete|
|CVE-2024-30171|Verification incomplete|
|CVE-2024-30172|Verification incomplete|
|CVE-2024-34447|Not found in dependency graph|
|CVE-2025-11226|Verification incomplete|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-22227|Verification incomplete|
|CVE-2025-22233|Verification incomplete|
|CVE-2025-41234|Verification incomplete|
|CVE-2025-41249|Verification incomplete|
|CVE-2025-48795|Verification incomplete|
|CVE-2025-48913|Not found in dependency graph|
|CVE-2025-48924|Verification incomplete|
|CVE-2025-55163|Not found in dependency graph|
|CVE-2025-58056|Not found in dependency graph|
|CVE-2025-58057|Not found in dependency graph|
|CVE-2025-7962|Not found in dependency graph|
|CVE-2025-8885|Verification incomplete|
