from __future__ import annotations

from parsers.gradle import parse_gradle_deps


def test_parse_gradle_deps_recognizes_parenthesized_gav_string():
    """Real-world gap: `implementation('group:artifact:version')` -- a
    parenthesized, single-quoted, full GAV coordinate string with no
    trailing block -- matched none of the three existing patterns (bare
    `config 'g:a:v'`, map-notation `config(group: 'g', name: 'a') { ... }`,
    or parenthesized `config('g:a') { strictly ... }`). A project declaring
    dependencies this way (observed live: cwih-cnp-mgmt-admin-api's
    tomcat-embed-* deps) got zero GradleDep entries for them, so the
    pipeline never saw them as direct dependencies and fell back to an
    ext-property force that Gradle's resolution ignores in favor of the
    (unpatched) explicit direct declaration -- CVEs stayed unfixed even
    though the pipeline reported the force as applied.
    """
    build_text = (
        "dependencies {\n"
        "    implementation('org.apache.tomcat.embed:tomcat-embed-core:10.1.52') "
        "//CVE-2025-61795\n"
        "    implementation ('org.apache.kafka:kafka-clients:4.1.2'){\n"
        "        exclude group: 'org.lz4', module: 'lz4-java'\n"
        "    }\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    by_artifact = {d.artifact: d for d in deps}

    assert "tomcat-embed-core" in by_artifact
    tomcat = by_artifact["tomcat-embed-core"]
    assert tomcat.group == "org.apache.tomcat.embed"
    assert tomcat.version == "10.1.52"
    assert "10.1.52" in tomcat.original

    assert "kafka-clients" in by_artifact
    kafka = by_artifact["kafka-clients"]
    assert kafka.group == "org.apache.kafka"
    assert kafka.version == "4.1.2"


def test_parse_gradle_deps_does_not_double_count_bare_and_map_style():
    """The new parenthesized-GAV pattern must not overlap with the existing
    bare-string or map-notation patterns for the same declaration."""
    build_text = (
        "dependencies {\n"
        "    implementation 'org.example:bare-dep:1.0.0'\n"
        "    implementation(group: 'org.example', name: 'map-dep') {\n"
        "        version { strictly '2.0.0' }\n"
        "    }\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    by_artifact = {d.artifact: d for d in deps}

    assert len(deps) == 2
    assert by_artifact["bare-dep"].version == "1.0.0"
    assert by_artifact["map-dep"].version == "2.0.0"


def test_parse_gradle_deps_recognizes_parenthesized_strictly_call():
    """Real-world gap: `version { strictly("1.10.1") }` -- strictly as a
    parenthesized call rather than `strictly 'v'` with bare whitespace --
    was invisible to _extract_strict_version's `\\bstrictly\\s+(['"])`
    regex, which requires the quote to follow whitespace directly. The
    whole GradleDep got dropped (version came back None), so this direct
    dependency never became a Case 1 write target and instead only got a
    resolutionStrategy.force entry -- which loses to the very
    `strictly(...)` constraint the parser couldn't see, leaving the old
    vulnerable version in place (observed live: cwih-cnp-mgmt-consent-
    publish-api's at.yawk.lz4:lz4-java stayed on 1.10.1 despite a force to
    1.11.1).
    """
    build_text = (
        "dependencies {\n"
        "    implementation(\"at.yawk.lz4:lz4-java\") {"
        "// fix of CVE-2025-66566\n"
        '        version { strictly("1.10.1") }\n'
        "    }\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    by_artifact = {d.artifact: d for d in deps}

    assert "lz4-java" in by_artifact
    lz4 = by_artifact["lz4-java"]
    assert lz4.group == "at.yawk.lz4"
    assert lz4.version == "1.10.1"


def test_parse_gradle_deps_recognizes_each_list_shared_strictly_block():
    """Real-world gap: a Groovy idiom pinning several same-group artifacts
    to one shared version in a single block --
    `['a', 'b'].each { implementation(group: 'g', name: it) { version { strictly 'v' } } }`.
    "name: it" is the loop variable, not a literal string, so it matched
    neither the map-notation nor parenthesized-string strict patterns; every
    artifact listed this way was invisible to parse_gradle_deps -- never a
    Case 1 direct-write target, never realigned by _align_competing_pins.
    resolutionStrategy.force was still written for them (as an unrelated
    sibling/Case 3 fallback), but real Gradle resolution kept the
    un-rewritten strictly value (strictly outranks force), leaving CVEs
    unfixed (observed live: cwih-cnp-mgmt-consent-api's netty-codec/
    netty-codec-http/netty-handler stayed on 4.1.132.Final with 19 CVEs
    remaining despite a force to 4.2.16.Final).
    """
    build_text = (
        "dependencies {\n"
        "    // --- Netty (Strict versions for vulnerability fixes) ---\n"
        "    ['netty-codec', 'netty-codec-http', 'netty-handler'].each {\n"
        "        implementation(group: 'io.netty', name: it) {\n"
        "            version { strictly '4.1.132.Final' }\n"
        "        }\n"
        "    }\n"
        "    implementation(group: 'io.netty', name: 'netty-codec-http2') {\n"
        "        version { strictly '4.2.10.Final' }\n"
        "    }\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    by_artifact = {d.artifact: d for d in deps}

    for name in ("netty-codec", "netty-codec-http", "netty-handler"):
        assert name in by_artifact, name
        dep = by_artifact[name]
        assert dep.group == "io.netty"
        assert dep.version == "4.1.132.Final"
        assert dep.config == "implementation"

    # The unrelated, separately-declared netty-codec-http2 must not be
    # swept into the loop's three entries.
    assert by_artifact["netty-codec-http2"].version == "4.2.10.Final"
    assert len([d for d in deps if d.artifact == "netty-codec-http2"]) == 1


def test_parse_gradle_deps_ignores_line_commented_declarations():
    """Real-world gap (observed live: ins-cp-mgmt-evaluation-workflow,
    ins-cp-mgmt-ecrdnc-workflow, ins-cp-mgmt-ecrphoneattribute-workflow): a
    dependency declaration commented out with `//` still contains the
    code-shaped substring `implementation 'g:a:v'`, which every pattern in
    parse_gradle_deps matched as if it were live. This produced a second,
    phantom GradleDep for org.apache.tomcat.embed:tomcat-embed-core
    alongside the real one, causing a duplicate row in
    gradle-version-changes.csv and, when write_gradle_file's rewrite loop
    ran against it, mutating the version number *inside the comment*
    instead of leaving dead code untouched.
    """
    build_text = (
        "dependencies {\n"
        "    implementation('org.apache.tomcat.embed:tomcat-embed-core:10.1.47')\n"
        "    //implementation 'org.apache.tomcat.embed:tomcat-embed-core:11.0.5'\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    matches = [d for d in deps if d.artifact == "tomcat-embed-core"]

    assert len(matches) == 1
    assert matches[0].version == "10.1.47"


def test_parse_gradle_deps_ignores_block_commented_declarations():
    build_text = (
        "dependencies {\n"
        "    implementation 'org.example:live-dep:1.0.0'\n"
        "    /* implementation 'org.example:live-dep:9.9.9' */\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    matches = [d for d in deps if d.artifact == "live-dep"]

    assert len(matches) == 1
    assert matches[0].version == "1.0.0"


def test_parse_gradle_deps_still_finds_strict_block_with_trailing_comment():
    """A comment after the closing brace on the same line (a common style
    in these real build files, e.g. `strictly '...' }//CVE-...`) must not
    blank out the real declaration itself -- only text after `//`."""
    build_text = (
        "dependencies {\n"
        "    implementation(group: 'io.netty', name: 'netty-codec-compression') {\n"
        "        version { strictly '4.2.16.Final' }//CVE-2025-58057\n"
        "    }\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    matches = [d for d in deps if d.artifact == "netty-codec-compression"]

    assert len(matches) == 1
    assert matches[0].version == "4.2.16.Final"


def test_parse_gradle_deps_ignores_commented_strictly_inside_live_block():
    """A commented-out alternate `strictly` line inside an otherwise-live
    block must not be picked up in place of the real one below it."""
    build_text = (
        "dependencies {\n"
        "    implementation(group: 'org.example', name: 'pinned') {\n"
        "        version {\n"
        "            // strictly '9.9.9'\n"
        "            strictly '1.2.3'\n"
        "        }\n"
        "    }\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    matches = [d for d in deps if d.artifact == "pinned"]

    assert len(matches) == 1
    assert matches[0].version == "1.2.3"


def test_parse_gradle_deps_does_not_treat_url_scheme_as_comment():
    """A `https://` URL inside a quoted string must not be misread as the
    start of a `//` comment, which would blank out everything after it on
    the line -- including a real dependency declaration on the same
    physical line."""
    build_text = (
        "repositories {\n"
        "    maven { url 'https://artifactory.example.com/repo' }\n"
        "}\n"
        "dependencies {\n"
        "    implementation 'org.example:after-url:2.0.0'\n"
        "}\n"
    )

    deps = parse_gradle_deps(build_text)
    matches = [d for d in deps if d.artifact == "after-url"]

    assert len(matches) == 1
    assert matches[0].version == "2.0.0"
