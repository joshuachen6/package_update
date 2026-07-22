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
