# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟡 Needs Review|
|Generated at|2026-07-28T09:01:02|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-phoneattribute-workflow.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/default-branch/ins-cp-mgmt-phoneattribute-workflow|
|Dependency files|1|
|Changed packages|20|
|Skipped packages|0|
|Validation records|1|
|Taskboard CVEs tracked|30|
|Resolved dependency changes|82|
|Verification classification|Partial - build passed but 1 CVE record(s) remain|
|Test verification|passed|
|Original CVEs remaining|1|
|JFrog vulnerabilities before|63|
|JFrog vulnerabilities after|1|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟡 **REVIEW RECOMMENDED**

The build passed, but some findings remain (unresolved CVE records and/or alternate versions selected during validation).

Review:
- the post-update JFrog audit for remaining CVE records
- build-validation-external-auto-fixes.csv (if present)

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|20|0|Written|Passed||Partial - build passed but 1 CVE record(s) remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|org.springframework:spring-context|gradle|6.2.0|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle|6.2.0|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle|3.3.0|3.3.16|Passed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle|6.2.0|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle|6.2.10|6.2.19|Passed|True|
|build.gradle|gradle|org.apache.kafka:kafka-clients|gradle|3.9.1|3.9.2|Passed|True|
|build.gradle|gradle|org.springframework:spring-webmvc|gradle|6.2.10|6.2.19|Passed|True|
|build.gradle|gradle|org.springframework:spring-beans|gradle|6.2.0|6.2.19|Passed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.13.14|1.17.0|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.3.12|4.5.13|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot-starter-actuator|gradle-force|3.3.12|3.5.16|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle-force|10.1.41|10.1.57|Passed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.3.12|3.5.13|Passed|True|
|build.gradle|gradle|org.apache.commons:commons-lang3|gradle-force|3.14.0|3.20.0|Passed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.3.12|3.5.16|Passed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.1.20|6.2.19|Passed|True|
|build.gradle|gradle|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|Passed|True|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|gradle-force|2.17.3|2.22.1|Passed|True|
|build.gradle|gradle|org.assertj:assertj-core|gradle-force|3.25.3|3.27.7|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle-force|10.1.41|10.1.57|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|dependency|blocked_version|forced_version|status|reason|source|
|---|---|---|---|---|---|
|com.fasterxml.jackson.core:jackson-databind||2.21.5|proactive_scan_force|forced to make the post-change dependency tree resolvable before the real build|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/logs/gradle-dependency-tree-before.txt|True|800|693|50600|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/logs/gradle-dependency-tree-after.txt|True|814|707|51134|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-phoneattribute-workflow_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java||1.10.1|added|
|ch.qos.logback:logback-classic|1.5.18|1.5.34|changed|
|ch.qos.logback:logback-core|1.5.18|1.5.34|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.17.3|2.22|changed|
|com.fasterxml.jackson.core:jackson-core|2.17.3|2.22.1|changed|
|com.fasterxml.jackson.core:jackson-databind|2.17.3|2.21.5|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.17.3|2.22.1|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jsr310|2.17.3|2.22.1|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.17.3|2.22.1|changed|
|com.fasterxml.jackson:jackson-bom|2.17.3|2.22.1|changed|
|com.fasterxml:classmate|1.7.0|1.7.3|changed|
|commons-codec:commons-codec|1.16.1|1.18.0|changed|
|io.micrometer:micrometer-commons|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-core|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-jakarta9|1.13.14|1.17.0|changed|
|io.micrometer:micrometer-observation|1.13.14|1.17.0|changed|
|io.projectreactor:reactor-core|3.6.17|3.7.19|changed|
|jakarta.activation:jakarta.activation-api|2.1.3|2.1.4|changed|
|jakarta.xml.bind:jakarta.xml.bind-api|4.0.2|4.0.5|changed|
|net.bytebuddy:byte-buddy|1.14.19|1.17.8|changed|
|net.bytebuddy:byte-buddy-agent|1.14.19|1.17.8|changed|
|org.apache.commons:commons-lang3|3.14.0|3.17.0|changed|
|org.apache.kafka:kafka-clients|3.9.1|3.9.2|changed|
|org.apache.logging.log4j:log4j-api|2.23.1|2.24.3|changed|
|org.apache.logging.log4j:log4j-to-slf4j|2.23.1|2.24.3|changed|
|org.apache.tomcat.embed:tomcat-embed-core|10.1.41|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.41|10.1.57|changed|
|org.apache.tomcat.embed:tomcat-embed-websocket|10.1.41|10.1.57|changed|
|org.apache.tomcat:tomcat-annotations-api|10.1.41|10.1.57|changed|
|org.aspectj:aspectjweaver|1.9.24|1.9.25.1|changed|
|org.assertj:assertj-core|3.25.3|3.27.7|changed|
|org.hamcrest:hamcrest|2.2|3.0|changed|
|org.hibernate.validator:hibernate-validator|8.0.2.Final|8.0.3.Final|changed|
|org.jboss.logging:jboss-logging|3.5.3.Final|3.6.3.Final|changed|
|org.jspecify:jspecify||1.0.0|added|
|org.junit.jupiter:junit-jupiter|5.10.5|5.12.2|changed|
|org.junit.jupiter:junit-jupiter-api|5.10.5|5.12.2|changed|
|org.junit.jupiter:junit-jupiter-engine|5.10.5|5.12.2|changed|
|org.junit.jupiter:junit-jupiter-params|5.10.5|5.12.2|changed|
|org.junit.platform:junit-platform-commons|1.10.5|1.12.2|changed|
|org.junit.platform:junit-platform-engine|1.10.5|1.12.2|changed|
|org.junit.platform:junit-platform-launcher||1.12.2|added|
|org.junit:junit-bom|5.10.5|5.12.2|changed|
|org.latencyutils:LatencyUtils|2.0.3||removed|
|org.lz4:lz4-java|1.8.0||removed|
|org.mockito:mockito-junit-jupiter|5.11.0|5.17.0|changed|
|org.mongodb:bson|5.0.1|5.5.2|changed|
|org.mongodb:bson-record-codec|5.0.1|5.5.2|changed|
|org.mongodb:mongodb-driver-core|5.0.1|5.5.2|changed|
|org.mongodb:mongodb-driver-sync|5.0.1|5.5.2|changed|
|org.projectlombok:lombok|1.18.38|1.18.46|changed|
|org.slf4j:jul-to-slf4j|2.0.17|2.0.18|changed|
|org.slf4j:slf4j-api|2.0.17|2.0.18|changed|
|org.springframework.boot:spring-boot|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator-autoconfigure|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-autoconfigure|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-actuator|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-mongodb|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-json|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-logging|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-tomcat|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-test|3.3.12|3.5.16|changed|
|org.springframework.boot:spring-boot-test-autoconfigure|3.3.12|3.5.16|changed|
|org.springframework.data:spring-data-commons|3.3.12|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.3.12|4.5.13|changed|
|org.springframework.kafka:spring-kafka|3.3.0|3.3.16|changed|
|org.springframework.retry:spring-retry|2.0.12|2.0.13|changed|
|org.springframework:spring-aop|6.1.20|6.2.19|changed|
|org.springframework:spring-beans|6.2.0|6.2.19|changed|
|org.springframework:spring-context|6.2.0|6.2.19|changed|
|org.springframework:spring-core|6.2.0|6.2.19|changed|
|org.springframework:spring-expression|6.2.0|6.2.19|changed|
|org.springframework:spring-jcl|6.1.20|6.2.19|changed|
|org.springframework:spring-messaging|6.1.20|6.2.19|changed|
|org.springframework:spring-test|6.1.20|6.2.19|changed|
|org.springframework:spring-tx|6.1.20|6.2.19|changed|
|org.springframework:spring-web|6.2.10|6.2.19|changed|
|org.springframework:spring-webflux|6.1.20|6.2.19|changed|
|org.springframework:spring-webmvc|6.2.10|6.2.19|changed|
|org.yaml:snakeyaml|2.2|2.4|changed|

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
|CVE-2025-22233|Verification incomplete|
|CVE-2025-3198|Not found in dependency graph|
|CVE-2025-41249|Verification incomplete|
|CVE-2025-48924|Verification incomplete|
|CVE-2025-48988|Verification incomplete|
|CVE-2025-48989|Verification incomplete|
|CVE-2025-49124|Verification incomplete|
|CVE-2025-49125|Verification incomplete|
|CVE-2025-5244|Not found in dependency graph|
|CVE-2025-5245|Not found in dependency graph|
|CVE-2025-52520|Verification incomplete|
|CVE-2025-53057|Not found in dependency graph|
|CVE-2025-53066|Not found in dependency graph|
|CVE-2025-53506|Not found in dependency graph|
|CVE-2025-55668|Verification incomplete|
|CVE-2025-55752|Verification incomplete|
|CVE-2025-55754|Verification incomplete|
|CVE-2025-61795|Verification incomplete|
|CVE-2025-6297|Not found in dependency graph|
|CVE-2025-7545|Not found in dependency graph|
|CVE-2025-8058|Not found in dependency graph|
|CVE-2025-8225|Not found in dependency graph|
|CVE-2025-9230|Not found in dependency graph|
