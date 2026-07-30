# Package Update Completion Report

## Summary
|metric|value|
|---|---|
|Overall Status|🟡 Needs Review|
|Generated at|2026-07-29T08:11:57|
|GitHub URL|https://github.com/Cloud-3-0-EMU/ins-cp-mgmt-cpms-epms-sync.git|
|Project directory|/Users/jchen18/.package_update_gui/repos/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/default-branch/ins-cp-mgmt-cpms-epms-sync|
|Dependency files|1|
|Changed packages|19|
|Skipped packages|0|
|Validation records|1|
|Taskboard CVEs tracked|0|
|Resolved dependency changes|28|
|Verification classification|Partial - build passed but 1 CVE record(s) remain|
|Test verification|passed|
|Original CVEs remaining|0|
|JFrog vulnerabilities before|23|
|JFrog vulnerabilities after|1|
|JFrog audit before JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/logs/jfrog-audit.json|
|JFrog audit after JSON|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/logs/jfrog-audit-after.json|

## Remediation Outcome

🟡 **REVIEW RECOMMENDED**

The build passed, but some findings remain (unresolved CVE records and/or alternate versions selected during validation).

Review:
- the post-update JFrog audit for remaining CVE records
- build-validation-external-auto-fixes.csv (if present)

## Dependency Files
|file|ecosystem|changes|skipped|write_status|validation_status|validation_message|verification_status|test_status|
|---|---|---|---|---|---|---|---|---|
|build.gradle|gradle|19|0|Written|Passed||Partial - build passed but 1 CVE record(s) remain|passed|

## Applied / Planned Changes
|file|ecosystem|package|type|old|new|status|remediation_guided|
|---|---|---|---|---|---|---|---|
|build.gradle|gradle|io.netty:netty-codec-http2|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle|10.1.55|11.0.24|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-websocket|gradle|11.0.18|11.0.24|Passed|True|
|build.gradle|gradle|org.apache.tomcat.embed:tomcat-embed-core|gradle|11.0.22|11.0.24|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-http|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-resolver-dns|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-dns|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-handler|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport-native-epoll|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-buffer|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-common|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-transport|gradle|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|at.yawk.lz4:lz4-java|gradle-force|1.10.1|1.11.1|Passed|True|
|build.gradle|gradle|ch.qos.logback:logback-core|gradle-force|1.5.32|1.6.1|Passed|True|
|build.gradle|gradle|io.netty:netty-handler-proxy|gradle-force|4.1.132.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|io.netty:netty-codec-compression|gradle-force|4.2.15.Final|4.2.16.Final|Passed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5|gradle-force||5.4.3|Passed|True|
|build.gradle|gradle|org.apache.httpcomponents.core5:httpcore5-h2|gradle-force||5.4.3|Passed|True|

## Skipped / Resolved / Could Not Update
_No rows._

## Build Validation
|dependency|blocked_version|forced_version|status|reason|source|
|---|---|---|---|---|---|
|com.fasterxml.jackson.core:jackson-databind|2.21.2|2.21.5|auto_forced_blocked_gradle_artifact|project build passed after replacing a blocked Gradle artifact with a non-vulnerable accessible fallback|build-validation-external-auto-fixes.csv|

## Before / After Dependency Trees
|ecosystem|snapshot|path|exists|line_count|dependency_count|bytes|
|---|---|---|---|---|---|---|
|gradle|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/logs/gradle-dependency-tree-before.txt|True|1238|1131|76311|
|gradle|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/logs/gradle-dependency-tree-after.txt|True|1258|1151|77387|
|node|before|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/logs/npm-dependency-tree-before.json|False|0|0|0|
|node|after|/Users/jchen18/Documents/package_update/logs/batch/Cloud-3-0-EMU_ins-cp-mgmt-cpms-epms-sync_default-branch/logs/npm-dependency-tree-after.json|False|0|0|0|

## Resolved Dependency Changes
|dependency|before|after|status|
|---|---|---|---|
|at.yawk.lz4:lz4-java|1.10.1|1.11.1|changed|
|ch.qos.logback:logback-classic|1.5.32|1.6.1|changed|
|ch.qos.logback:logback-core|1.5.32|1.6.1|changed|
|com.fasterxml.jackson.core:jackson-databind||2.21.5|added|
|com.fasterxml.jackson:jackson-bom|2.21.2|2.21.5|changed|
|io.netty:netty-buffer|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-base|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-compression|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-dns|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-http2|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-marshalling|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-protobuf|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-codec-socks|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-common|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-handler|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-handler-proxy|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-classes-macos|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-resolver-dns-native-macos|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-transport|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-transport-classes-epoll|4.1.132.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-epoll|4.2.15.Final|4.2.16.Final|changed|
|io.netty:netty-transport-native-unix-common|4.1.132.Final|4.2.16.Final|changed|
|org.apache.tomcat.embed:tomcat-embed-core|11.0.22|11.0.24|changed|
|org.apache.tomcat.embed:tomcat-embed-websocket|11.0.18|11.0.24|changed|
