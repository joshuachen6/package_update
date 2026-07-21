# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟢 Success|
|Generated at|2026-07-18T14:46:38|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-admin-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/cwih-cnp-mgmt-admin-api|
|Dependency files|1|
|Changed packages|17|
|Skipped packages|0|
|Validation records|0|
|Taskboard CVEs tracked|5|
|Resolved dependency changes|42|
|JFrog vulnerabilities|58|
|JFrog audit JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api/logs/jfrog-audit.json|

## Remediation Outcome

🟢 **SUCCESS**

All remediation actions completed successfully.

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|
|---|---|---|---|---|---|---|
|build.gradle|gradle|17|0||||

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.18|6.2.19|Planned|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle|6.2.18|6.2.19|Planned|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.32|1.5.38|Planned|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.52|10.1.57|Planned|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.11|3.5.13|Planned|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle-force|3.3.15|3.3.16|Planned|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.11|4.5.13|Planned|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.52|10.1.57|Planned|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.132.Final|4.2.16.Final|Planned|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.21.2|2.22.1|Planned|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
_No rows._

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api/logs/gradle-dependency-tree-before.txt|True|1332|1225|84614|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api/logs/gradle-dependency-tree-after.txt|True|311|285|20130|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-admin-api/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|com.jayway.jsonpath:json-path|2.9.0||removed|
|com.vaadin.external.google:android-json|0.0.20131108.vaadin1||removed|
|net.bytebuddy:byte-buddy|1.17.8||removed|
|net.bytebuddy:byte-buddy-agent|1.17.8||removed|
|net.minidev:accessors-smart|2.5.2||removed|
|net.minidev:json-smart|2.5.2||removed|
|org.apiguardian:apiguardian-api|1.1.2||removed|
|org.assertj:assertj-core|3.27.7||removed|
|org.awaitility:awaitility|4.2.2||removed|
|org.hamcrest:hamcrest|3.0||removed|
|org.junit.jupiter:junit-jupiter|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-api|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-engine|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-params|5.12.2||removed|
|org.junit.platform:junit-platform-commons|1.12.2||removed|
|org.junit.platform:junit-platform-engine|1.12.2||removed|
|org.junit.platform:junit-platform-launcher|1.12.2||removed|
|org.junit:junit-bom|5.12.2||removed|
|org.mockito:mockito-core|5.19.0||removed|
|org.mockito:mockito-inline|5.2.0||removed|
|org.mockito:mockito-junit-jupiter|5.17.0||removed|
|org.objenesis:objenesis|3.3||removed|
|org.opentest4j:opentest4j|1.3.0||removed|
|org.ow2.asm:asm|9.7.1||removed|
|org.projectlombok:lombok|1.18.46||removed|
|org.skyscreamer:jsonassert|1.5.3||removed|
|org.springframework.boot:spring-boot-starter-test|3.5.14||removed|
|org.springframework.boot:spring-boot-test|3.5.14||removed|
|org.springframework.boot:spring-boot-test-autoconfigure|3.5.14||removed|
|org.springframework:spring-aop|6.2.18|6.2.19|changed|
|org.springframework:spring-beans|6.2.18|6.2.19|changed|
|org.springframework:spring-context|6.2.18|6.2.19|changed|
|org.springframework:spring-core|6.2.18|6.2.19|changed|
|org.springframework:spring-expression|6.2.18|6.2.19|changed|
|org.springframework:spring-jcl|6.2.18|6.2.19|changed|
|org.springframework:spring-messaging|6.2.18|6.2.19|changed|
|org.springframework:spring-test|6.2.18||removed|
|org.springframework:spring-tx|6.2.18|6.2.19|changed|
|org.springframework:spring-web|6.2.18|6.2.19|changed|
|org.springframework:spring-webflux|6.2.18|6.2.19|changed|
|org.springframework:spring-webmvc|6.2.18|6.2.19|changed|
|org.xmlunit:xmlunit-core|2.10.4||removed|

## Taskboard CVEs
|cve_id|status|
|---|---|
|CVE-2025-11226|Not found in dependency graph|
|CVE-2025-11839|Not found in dependency graph|
|CVE-2025-11840|Not found in dependency graph|
|CVE-2025-27789|Not found in dependency graph|
|CVE-2025-61795|Not found in dependency graph|
