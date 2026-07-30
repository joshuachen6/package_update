# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🔴 Manual Update Required|
|Generated at|2026-07-29T07:48:02|
|GitHub URL|https://github.com/Cloud-3-0-EMU/cwih-cnp-mgmt-dnc-publish-api.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/default-branch/cwih-cnp-mgmt-dnc-publish-api|
|Dependency files|1|
|Changed packages|33|
|Skipped packages|4|
|Validation records|34|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|188|
|Verification classification|Failed - dependency updates could not be validated; manual review required|
|Test verification|not_run|
|Original CVEs remaining|98|
|JFrog vulnerabilities before|104|
|JFrog vulnerabilities after|104|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/logs/jfrog-audit-after.json|

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
|build.gradle|gradle|org.bouncycastle:bcprov-jdk18on|gradle|1.80|1.85|Failed|True|
|build.gradle|gradle|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework.kafka:spring-kafka|gradle|3.3.6|3.3.16|Failed|True|
|build.gradle|gradle|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|Failed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.18|11.0.24|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.25|1.6.1|Failed|True|
|build.gradle|gradle|org.apache.cxf:cxf-core|gradle-force|4.1.3|4.2.2|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle-force|4.2.5.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.3|Failed|True|
|build.gradle|gradle|io.micrometer:micrometer-core|gradle-force|1.15.10|1.17.0|Failed|True|
|build.gradle|gradle|org.springframework.boot:spring-boot|gradle-force|3.5.12|3.5.16|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-commons|gradle-force|3.5.10|3.5.13|Failed|True|
|build.gradle|gradle|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.2|2.5.3|Failed|True|
|build.gradle|gradle|org.springframework.data:spring-data-mongodb|gradle-force|4.5.10|4.5.13|Failed|True|
|build.gradle|gradle|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5|gradle-force|5.3.6|5.4.3|Failed|True|
|build.gradle|gradle|commons-beanutils:commons-beanutils|gradle-force|1.9.4|1.11.0|Failed|True|
|build.gradle|gradle|org.codehaus.plexus:plexus-utils|gradle-force|3.5.1|3.6.1|Failed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force|5.3.6|5.4.3|Failed|True|
|build.gradle|gradle|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|org.springframework:spring-webflux|gradle-force|6.2.17|6.2.19|Failed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle-force|4.1.127.Final|4.2.16.Final|Failed|True|

## Skipped / Resolved / Could Not Update
|file|ecosystem|package|current|target|status|reason|detail|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|com.fasterxml.jackson.core:jackson-databind|${jacksonVersion}||Skipped|unparseable version||
|build.gradle|gradle|io.netty:netty-codec|${nettyVersion}||Skipped|unparseable version||
|build.gradle|gradle|io.netty:netty-codec-http2|${nettyVersion}||Skipped|unparseable version||
|build.gradle|gradle|io.netty:netty-handler|${nettyVersion}||Skipped|unparseable version||

## Build Validation
|package|change_type|old|new|status|reason|source|
|---|---|---|---|---|---|---|
|org.bouncycastle:bcprov-jdk18on|gradle|1.80|1.85|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|com.github.jknack:handlebars|gradle|4.4.0|4.5.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-framework.version|gradle|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-webflux|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-web|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-expression|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework:spring-core|gradle-force|6.2.17|6.2.19|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.hateoas:spring-hateoas|gradle-force|2.5.2|2.5.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-mongodb|gradle-force|4.5.10|4.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.data:spring-data-commons|gradle-force|3.5.10|3.5.13|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.boot:spring-boot|gradle-force|3.5.12|3.5.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.springframework.kafka:spring-kafka|gradle|3.3.6|3.3.16|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.lz4:lz4-java|gradle-force|1.8.0|1.8.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.codehaus.plexus:plexus-utils|gradle-force|3.5.1|3.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.neethi:neethi|gradle-force|3.2.1|3.2.3|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
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
|commons-beanutils:commons-beanutils|gradle-force|1.9.4|1.11.0|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|ch.qos.logback:logback-core|gradle-force|1.5.25|1.6.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.18|11.0.24|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.kafka:kafka-clients|gradle|4.0.0|4.3.1|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|org.apache.cxf:cxf-rt-transports-http|gradle|4.1.3|4.2.2|manual_update_required|build validation failed and failure isolation disabled|build-validation-manual-updates.csv|
|||||proactive_force|blocked transitive detected in post-change dependency tree|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/logs/gradle-dependency-tree-before.txt|True|2432|2317|163417|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/logs/gradle-dependency-tree-after.txt|True|599|573|40582|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_cwih-cnp-mgmt-dnc-publish-api_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java||1.10.2|added|
|ch.qos.logback:logback-classic|1.5.25|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.25|1.6.1|changed|
|com.fasterxml.jackson.core:jackson-annotations|2.19.4|2.21|changed|
|com.fasterxml.jackson.core:jackson-core|2.19.4|2.21.4|changed|
|com.fasterxml.jackson.core:jackson-databind|2.19.4|2.21.4|changed|
|com.fasterxml.jackson.dataformat:jackson-dataformat-yaml|2.19.4|2.21.4|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jdk8|2.19.4|2.21.4|changed|
|com.fasterxml.jackson.datatype:jackson-datatype-jsr310|2.19.4|2.21.4|changed|
|com.fasterxml.jackson.module:jackson-module-parameter-names|2.19.4|2.21.4|changed|
|com.fasterxml.jackson:jackson-bom|2.19.4|2.21.4|changed|
|com.fasterxml.woodstox:woodstox-core|7.1.1|7.2.0|changed|
|com.github.jknack:handlebars|4.4.0||removed|
|com.github.luben:zstd-jni|1.5.6-6|1.5.6-10|changed|
|com.github.tomakehurst:wiremock-jre8-standalone|2.35.1||removed|
|com.google.errorprone:error_prone_annotations|2.36.0||removed|
|com.google.guava:failureaccess|1.0.3||removed|
|com.google.guava:guava|33.4.8-jre||removed|
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
|commons-collections:commons-collections|3.2.2||removed|
|commons-logging:commons-logging|1.2||removed|
|dk.brics:automaton|1.12-4||removed|
|io.micrometer:context-propagation|1.1.4|1.2.1|changed|
|io.micrometer:micrometer-commons|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-core|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-jakarta9|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-observation|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-registry-prometheus|1.15.10|1.17.0|changed|
|io.micrometer:micrometer-tracing|1.5.10|1.5.12|changed|
|io.micrometer:micrometer-tracing-bridge-brave|1.5.10|1.5.12|changed|
|io.netty.incubator:netty-incubator-codec-classes-quic|0.0.74.Final||removed|
|io.netty.incubator:netty-incubator-codec-native-quic|0.0.74.Final||removed|
|io.netty:netty-codec-base|4.2.5.Final|4.2.16.Final|changed|
|io.netty:netty-codec-compression|4.2.5.Final|4.2.16.Final|changed|
|io.projectreactor.netty.incubator:reactor-netty-incubator-quic|0.2.16||removed|
|io.projectreactor.netty:reactor-netty|1.2.16|1.2.18|changed|
|io.projectreactor.netty:reactor-netty-core|1.2.16|1.2.18|changed|
|io.projectreactor.netty:reactor-netty-http|1.2.16|1.2.18|changed|
|io.projectreactor:reactor-core|3.7.17|3.7.19|changed|
|io.projectreactor:reactor-test|3.7.17||removed|
|jakarta.xml.bind:jakarta.xml.bind-api|4.0.4|4.0.5|changed|
|javax.annotation:jsr250-api|1.0||removed|
|javax.enterprise:cdi-api|1.0||removed|
|net.bytebuddy:byte-buddy|1.17.8||removed|
|net.bytebuddy:byte-buddy-agent|1.17.8||removed|
|net.java.dev.jna:jna-platform|5.13.0||removed|
|net.javacrumbs.json-unit:json-unit-assertj|2.38.0||removed|
|net.javacrumbs.json-unit:json-unit-core|2.38.0||removed|
|net.javacrumbs.json-unit:json-unit-json-path|2.38.0||removed|
|org.apache.commons:commons-text|1.11.0||removed|
|org.apache.cxf:cxf-core|4.1.3|4.2.2|changed|
|org.apache.cxf:cxf-rt-transports-http|4.1.3|4.2.2|changed|
|org.apache.groovy:groovy|4.0.30||removed|
|org.apache.groovy:groovy-bom|4.0.30||removed|
|org.apache.groovy:groovy-json|4.0.30||removed|
|org.apache.groovy:groovy-nio|4.0.30||removed|
|org.apache.groovy:groovy-xml|4.0.30||removed|
|org.apache.httpcomponents.client5:httpclient5|5.5.2||removed|
|org.apache.httpcomponents.core5:httpcore5|5.3.6||removed|
|org.apache.httpcomponents.core5:httpcore5-h2|5.3.6||removed|
|org.apache.httpcomponents:httpclient|4.5.14||removed|
|org.apache.httpcomponents:httpcore|4.4.16||removed|
|org.apache.kafka:kafka-clients|4.0.0|4.3.1|changed|
|org.apache.maven.resolver:maven-resolver-api|1.9.22||removed|
|org.apache.maven.resolver:maven-resolver-connector-basic|1.9.22||removed|
|org.apache.maven.resolver:maven-resolver-impl|1.9.22||removed|
|org.apache.maven.resolver:maven-resolver-named-locks|1.9.22||removed|
|org.apache.maven.resolver:maven-resolver-spi|1.9.22||removed|
|org.apache.maven.resolver:maven-resolver-transport-http|1.9.22||removed|
|org.apache.maven.resolver:maven-resolver-util|1.9.22||removed|
|org.apache.maven:maven-artifact|3.9.9||removed|
|org.apache.maven:maven-builder-support|3.9.9||removed|
|org.apache.maven:maven-model|3.9.9||removed|
|org.apache.maven:maven-model-builder|3.9.9||removed|
|org.apache.maven:maven-repository-metadata|3.9.9||removed|
|org.apache.maven:maven-resolver-provider|3.9.9||removed|
|org.apache.neethi:neethi|3.2.1|3.2.3|changed|
|org.apache.tomcat.embed:tomcat-embed-core|11.0.18|11.0.24|changed|
|org.apache.tomcat.embed:tomcat-embed-el|10.1.52|10.1.55|changed|
|org.apache.tomcat:tomcat-annotations-api|10.1.52|10.1.55|changed|
|org.apache.ws.xmlschema:xmlschema-core|2.3.1|2.3.2|changed|
|org.apiguardian:apiguardian-api|1.1.2||removed|
|org.assertj:assertj-core|3.27.7||removed|
|org.awaitility:awaitility|4.2.2||removed|
|org.bouncycastle:bcprov-jdk18on|1.81||removed|
|org.codehaus.plexus:plexus-classworlds|2.5.2||removed|
|org.codehaus.plexus:plexus-component-annotations|1.5.5||removed|
|org.codehaus.plexus:plexus-interpolation|1.27||removed|
|org.codehaus.plexus:plexus-utils|3.5.1||removed|
|org.codehaus.woodstox:stax2-api|4.2.2|4.3.0|changed|
|org.eclipse.jgit:org.eclipse.jgit|6.10.1.202505221210-r||removed|
|org.eclipse.jgit:org.eclipse.jgit.ssh.jsch|6.7.0.202309050840-r||removed|
|org.eclipse.sisu:org.eclipse.sisu.inject|0.9.0.M3||removed|
|org.eclipse.sisu:org.eclipse.sisu.plexus|0.3.0||removed|
|org.glassfish.jaxb:jaxb-core|4.0.6|4.0.9|changed|
|org.glassfish.jaxb:jaxb-runtime|4.0.6|4.0.9|changed|
|org.glassfish.jaxb:txw2|4.0.6|4.0.9|changed|
|org.hamcrest:hamcrest|3.0||removed|
|org.hamcrest:hamcrest-core|3.0||removed|
|org.junit.jupiter:junit-jupiter|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-api|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-engine|5.12.2||removed|
|org.junit.jupiter:junit-jupiter-params|5.12.2||removed|
|org.junit.platform:junit-platform-commons|1.12.2||removed|
|org.junit.platform:junit-platform-engine|1.12.2||removed|
|org.junit.platform:junit-platform-launcher|1.12.2||removed|
|org.junit:junit-bom|5.12.2||removed|
|org.latencyutils:LatencyUtils|2.0.3||removed|
|org.lz4:lz4-java|1.8.0||removed|
|org.mockito:mockito-core|5.17.0||removed|
|org.mockito:mockito-junit-jupiter|5.17.0||removed|
|org.objenesis:objenesis|3.3||removed|
|org.openjdk.nashorn:nashorn-core|15.4||removed|
|org.opentest4j:opentest4j|1.3.0||removed|
|org.ow2.asm:asm-analysis|7.3.1||removed|
|org.ow2.asm:asm-commons|7.3.1||removed|
|org.ow2.asm:asm-tree|7.3.1||removed|
|org.ow2.asm:asm-util|7.3.1||removed|
|org.projectlombok:lombok|1.18.44|1.18.46|changed|
|org.skyscreamer:jsonassert|1.5.3||removed|
|org.slf4j:jul-to-slf4j|2.0.17|2.0.18|changed|
|org.slf4j:slf4j-api|2.0.17|2.0.18|changed|
|org.sonatype.sisu:sisu-guice|3.2.5||removed|
|org.sonatype.sisu:sisu-inject-bean|2.6.0||removed|
|org.sonatype.sisu:sisu-inject-plexus|2.6.0||removed|
|org.springframework.boot:spring-boot|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-actuator-autoconfigure|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-autoconfigure|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-configuration-processor|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-actuator|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-aop|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-mongodb|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-data-redis-reactive|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-hateoas|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-json|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-logging|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-reactor-netty|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-test|3.5.12||removed|
|org.springframework.boot:spring-boot-starter-validation|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-starter-webflux|3.5.12|3.5.16|changed|
|org.springframework.boot:spring-boot-test|3.5.12||removed|
|org.springframework.boot:spring-boot-test-autoconfigure|3.5.12||removed|
|org.springframework.cloud:spring-cloud-contract-converters|4.3.0||removed|
|org.springframework.cloud:spring-cloud-contract-spec|4.3.0||removed|
|org.springframework.cloud:spring-cloud-contract-spec-groovy|4.3.0||removed|
|org.springframework.cloud:spring-cloud-contract-spec-java|4.3.0||removed|
|org.springframework.cloud:spring-cloud-contract-stub-runner|4.3.0||removed|
|org.springframework.cloud:spring-cloud-contract-verifier|4.3.0||removed|
|org.springframework.cloud:spring-cloud-contract-wiremock|4.3.0||removed|
|org.springframework.cloud:spring-cloud-starter-contract-stub-runner|4.2.1||removed|
|org.springframework.cloud:spring-cloud-test-support|4.3.0||removed|
|org.springframework.data:spring-data-commons|3.5.10|3.5.13|changed|
|org.springframework.data:spring-data-keyvalue|3.5.10|3.5.13|changed|
|org.springframework.data:spring-data-mongodb|4.5.10|4.5.13|changed|
|org.springframework.data:spring-data-redis|3.5.10|3.5.13|changed|
|org.springframework.hateoas:spring-hateoas|2.5.2|2.5.3|changed|
|org.springframework.kafka:spring-kafka|3.3.6|3.3.16|changed|
|org.springframework.security:spring-security-crypto|6.5.9|6.5.11|changed|
|org.springframework:spring-aop|6.2.17|6.2.19|changed|
|org.springframework:spring-beans|6.2.17|6.2.19|changed|
|org.springframework:spring-context|6.2.17|6.2.19|changed|
|org.springframework:spring-context-support|6.2.17|6.2.19|changed|
|org.springframework:spring-core|6.2.17|6.2.19|changed|
|org.springframework:spring-expression|6.2.17|6.2.19|changed|
|org.springframework:spring-jcl|6.2.17|6.2.19|changed|
|org.springframework:spring-messaging|6.2.17|6.2.19|changed|
|org.springframework:spring-oxm|6.2.17|6.2.19|changed|
|org.springframework:spring-test|6.2.17||removed|
|org.springframework:spring-tx|6.2.17|6.2.19|changed|
|org.springframework:spring-web|6.2.17|6.2.19|changed|
|org.springframework:spring-webflux|6.2.17|6.2.19|changed|
|org.xerial.snappy:snappy-java|1.1.10.5|1.1.10.7|changed|
|org.xmlunit:xmlunit-core|2.10.4||removed|
