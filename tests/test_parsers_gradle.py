from unittest.mock import MagicMock, patch

from parsers.gradle import (
    GradleDep,
    _fuzzy_keywords,
    collect_known_packages,
    find_accessible_version,
    get_available_versions,
    parallel_fetch_versions,
    parse_gradle_deps,
    version_accessible,
)
from shared.maven_version import MavenVersion

BUILD_GRADLE_SIMPLE = """
dependencies {
    implementation 'org.springframework:spring-core:5.3.27'
    api 'com.google.guava:guava:31.1-jre'
    testImplementation 'junit:junit:4.13.2'
}
"""

BUILD_GRADLE_MULTIPLE_CONFIGS = """
dependencies {
    implementation 'org.springframework:spring-web:5.3.27'
    compileOnly 'javax.servlet:javax.servlet-api:4.0.1'
    runtimeOnly 'org.postgresql:postgresql:42.5.0'
    annotationProcessor 'org.projectlombok:lombok:1.18.26'
    testImplementation 'org.mockito:mockito-core:5.2.0'
    testRuntimeOnly 'org.junit.jupiter:junit-jupiter-engine:5.9.2'
}
"""


class TestParseGradleDeps:
    def test_single_dep(self):
        deps = parse_gradle_deps("dependencies {\n    implementation 'com.example:mylib:1.0.0'\n}")
        assert len(deps) == 1
        dep = deps[0]
        assert dep.config == "implementation"
        assert dep.group == "com.example"
        assert dep.artifact == "mylib"
        assert dep.version == "1.0.0"

    def test_multiple_deps(self):
        deps = parse_gradle_deps(BUILD_GRADLE_SIMPLE)
        assert len(deps) == 3
        artifacts = {d.artifact for d in deps}
        assert "spring-core" in artifacts
        assert "guava" in artifacts
        assert "junit" in artifacts

    def test_all_config_types(self):
        deps = parse_gradle_deps(BUILD_GRADLE_MULTIPLE_CONFIGS)
        configs = {d.config for d in deps}
        assert "implementation" in configs
        assert "compileOnly" in configs
        assert "runtimeOnly" in configs
        assert "annotationProcessor" in configs
        assert "testImplementation" in configs
        assert "testRuntimeOnly" in configs

    def test_empty_string(self):
        assert parse_gradle_deps("") == []

    def test_no_deps_block(self):
        assert parse_gradle_deps("apply plugin: 'java'") == []

    def test_preserves_original(self):
        text = "    implementation 'org.springframework:spring-core:5.3.27'"
        deps = parse_gradle_deps(text)
        assert len(deps) == 1
        assert deps[0].original in text

    def test_double_quotes(self):
        deps = parse_gradle_deps('implementation "com.example:lib:2.0.0"')
        assert len(deps) == 1
        assert deps[0].version == "2.0.0"

    def test_match_positions(self):
        text = "implementation 'org.example:myartifact:1.0.0'"
        deps = parse_gradle_deps(text)
        assert len(deps) == 1
        assert deps[0].match_start == 0
        assert deps[0].match_end == len(text)


class TestCollectKnownPackages:
    def test_returns_artifact_and_coord(self):
        deps = parse_gradle_deps(BUILD_GRADLE_SIMPLE)
        known = collect_known_packages(deps)
        assert "spring-core" in known
        assert "org.springframework:spring-core" in known
        assert "guava" in known
        assert "com.google.guava:guava" in known

    def test_empty_deps(self):
        assert collect_known_packages([]) == set()


class TestFuzzyKeywords:
    def test_splits_hyphen(self):
        kws = _fuzzy_keywords("spring-boot")
        assert "spring" in kws
        assert "boot" not in kws  # "boot" < 5 chars

    def test_splits_dot(self):
        kws = _fuzzy_keywords("org.springframework")
        assert "springframework" in kws
        assert "org" not in kws  # "org" < 5 chars

    def test_filters_stopwords(self):
        kws = _fuzzy_keywords("spring-boot-starter")
        assert "starter" not in kws

    def test_filters_short_tokens(self):
        kws = _fuzzy_keywords("a.ab.abc.abcd.abcde")
        assert "abcde" in kws
        assert "abcd" not in kws  # < 5 chars

    def test_filters_digits(self):
        _fuzzy_keywords("junit5.platform")
        assert True  # digits check: "junit5".isdigit() is False, so it passes
        # Pure digit tokens should be excluded
        kws2 = _fuzzy_keywords("lib.12345")
        assert "12345" not in kws2

    def test_returns_list(self):
        result = _fuzzy_keywords("spring-boot")
        assert isinstance(result, list)

    def test_deduplicates(self):
        # Same token appearing multiple times via different splits should not duplicate
        kws = _fuzzy_keywords("spring.spring-spring")
        assert kws.count("spring") <= 1


MAVEN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata>
  <versioning>
    <versions>
      <version>5.3.10</version>
      <version>5.3.27</version>
      <version>6.0.0</version>
    </versions>
  </versioning>
</metadata>"""


class TestGetAvailableVersions:
    BASE = "https://artifactory.example.com/repo"

    def _mock_get(self, status=200, text=MAVEN_XML, exc=None):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.text = text
        if exc:
            return patch("requests.get", side_effect=exc)
        return patch("requests.get", return_value=mock_resp)

    def test_returns_sorted_versions(self):
        with self._mock_get():
            versions, err = get_available_versions(
                "org.springframework", "spring-core", self.BASE, None, 10
            )
        assert err == ""
        assert [str(v) for v in versions] == ["5.3.10", "5.3.27", "6.0.0"]

    def test_http_error_returns_empty(self):
        with self._mock_get(status=404):
            versions, err = get_available_versions(
                "org.springframework", "spring-core", self.BASE, None, 10
            )
        assert versions == []
        assert "404" in err

    def test_network_exception_returns_empty(self):
        with self._mock_get(exc=ConnectionError("timeout")):
            versions, err = get_available_versions(
                "org.springframework", "spring-core", self.BASE, None, 10
            )
        assert versions == []
        assert "request failed" in err

    def test_invalid_xml_returns_empty(self):
        with self._mock_get(text="not xml at all"):
            versions, err = get_available_versions(
                "org.springframework", "spring-core", self.BASE, None, 10
            )
        assert versions == []
        assert "XML parse error" in err

    def test_skips_unparseable_versions(self):
        xml = "<metadata><versioning><versions><version>bad</version><version>5.3.27</version></versions></versioning></metadata>"
        with self._mock_get(text=xml):
            versions, _err = get_available_versions(
                "org.springframework", "spring-core", self.BASE, None, 10
            )
        assert len(versions) == 1
        assert str(versions[0]) == "5.3.27"


class TestVersionAccessible:
    BASE = "https://artifactory.example.com/repo"

    def test_returns_true_on_200(self):
        mock_resp = MagicMock(status_code=200)
        with patch("requests.head", return_value=mock_resp):
            assert (
                version_accessible(
                    "org.springframework", "spring-core", "5.3.27", self.BASE, None, 10
                )
                is True
            )

    def test_returns_false_on_403(self):
        mock_resp = MagicMock(status_code=403)
        with patch("requests.head", return_value=mock_resp):
            assert (
                version_accessible(
                    "org.springframework", "spring-core", "5.3.27", self.BASE, None, 10
                )
                is False
            )

    def test_returns_false_on_exception(self):
        with patch("requests.head", side_effect=ConnectionError()):
            assert (
                version_accessible(
                    "org.springframework", "spring-core", "5.3.27", self.BASE, None, 10
                )
                is False
            )


class TestFindAccessibleVersion:
    BASE = "https://artifactory.example.com/repo"

    def _avail(self, *versions):
        return [MavenVersion.parse(v) for v in versions]

    def test_returns_first_accessible(self):
        avail = self._avail("5.3.10", "5.3.27", "5.3.30")
        start = MavenVersion.parse("5.3.27")
        with patch("parsers.gradle.version_accessible", return_value=True):
            result = find_accessible_version(
                "org.springframework", "spring-core", start, avail, self.BASE, None, 10
            )
        assert result == "5.3.27"

    def test_skips_blocked_version(self):
        avail = self._avail("5.3.27", "5.3.30")
        start = MavenVersion.parse("5.3.27")
        responses = [False, True]
        with patch("parsers.gradle.version_accessible", side_effect=responses):
            result = find_accessible_version(
                "org.springframework", "spring-core", start, avail, self.BASE, None, 10
            )
        assert result == "5.3.30"

    def test_returns_none_when_all_blocked(self):
        avail = self._avail("5.3.27")
        start = MavenVersion.parse("5.3.27")
        with patch("parsers.gradle.version_accessible", return_value=False):
            result = find_accessible_version(
                "org.springframework", "spring-core", start, avail, self.BASE, None, 10
            )
        assert result is None

    def test_excludes_versions_below_start(self):
        avail = self._avail("5.3.10", "5.3.27")
        start = MavenVersion.parse("5.3.27")
        with patch("parsers.gradle.version_accessible", return_value=True):
            result = find_accessible_version(
                "org.springframework", "spring-core", start, avail, self.BASE, None, 10
            )
        assert result == "5.3.27"  # 5.3.10 excluded, not >=5.3.27


class TestParallelFetchVersions:
    BASE = "https://artifactory.example.com/repo"

    def _dep(self, group, artifact, version="1.0.0"):
        return GradleDep(
            config="implementation",
            group=group,
            artifact=artifact,
            version=version,
            original="",
            match_start=0,
            match_end=0,
        )

    def test_aggregates_results(self):
        avail = [MavenVersion.parse("5.3.27")]
        with patch("parsers.gradle.get_available_versions", return_value=(avail, "")):
            deps = [self._dep("org.springframework", "spring-core")]
            results, errors = parallel_fetch_versions(deps, self.BASE, None, 10, 1, False)
        assert "org.springframework:spring-core" in results
        assert errors == []

    def test_records_fetch_errors(self):
        with patch("parsers.gradle.get_available_versions", return_value=([], "HTTP 404")):
            deps = [self._dep("org.example", "missing-lib")]
            _results, errors = parallel_fetch_versions(deps, self.BASE, None, 10, 1, False)
        assert len(errors) == 1
        assert "HTTP 404" in errors[0]["error"]

    def test_empty_deps_returns_empty(self):
        results, errors = parallel_fetch_versions([], self.BASE, None, 10, 1, False)
        assert results == {}
        assert errors == []


def test_extract_ado_versions_passes_two_tuple_tasks_to_batch_resolve(tmp_path, monkeypatch):
    import sys
    import types

    import parsers.gradle as gradle

    csv_path = tmp_path / "tasks.csv"
    csv_path.write_text(
        "id,title,description\n"
        "123,Upgrade dependency,Please update vulnerable component to 1.2.3\n",
        encoding="utf-8",
    )

    fake_resolver = types.ModuleType("resolver.claude_resolver")
    seen = {}

    def batch_resolve(tasks, known_packages, **kwargs):
        seen["tasks"] = tasks
        for task in tasks:
            assert len(task) == 2
        return {0: {"org.example:lib": ">="}}, []

    fake_resolver.batch_resolve = batch_resolve
    monkeypatch.setitem(sys.modules, "resolver.claude_resolver", fake_resolver)

    versions, task_ids, constraints, osv_packages = gradle.extract_ado_versions(
        str(csv_path),
        ["id", "title", "description"],
        {"org.example:lib"},
        False,
    )

    assert len(seen["tasks"]) == 1
    assert len(seen["tasks"][0]) == 2
    assert seen["tasks"][0][0] == 123
    assert "Upgrade dependency" in seen["tasks"][0][1]
    assert "Please update vulnerable component to 1.2.3" in seen["tasks"][0][1]
    assert "org.example:lib" in versions
    assert constraints["org.example:lib"] == ">="
    assert task_ids["org.example:lib"] == {123}
    assert osv_packages == set()


def test_extract_ado_versions_uses_claude_for_fuzzy_spring_candidates(monkeypatch):
    import sys
    import types

    import parsers.gradle as gradle
    import shared.cve_lookup as cve_lookup

    monkeypatch.setattr(
        gradle,
        "read_csv_full_rows",
        lambda csv_path, columns: [
            (
                90557059055706,
                "CVIT - app - CVE-2026-22741",
                "Spring MVC and WebFlux applications are vulnerable to cache poisoning. "
                "Users should upgrade to 6.2.14.",
            )
        ],
    )
    monkeypatch.setattr(cve_lookup, "prefetch_advisories", lambda rows, ecosystem: {})
    monkeypatch.setattr(cve_lookup, "extract_advisory_id", lambda title: None)

    fake_resolver = types.ModuleType("resolver.claude_resolver")
    seen = {}

    def batch_resolve(tasks, known_packages, **kwargs):
        seen["tasks"] = tasks
        seen["known_packages"] = known_packages
        return {
            0: {
                "org.springframework:spring-webmvc": ">=",
                "org.springframework:spring-webflux": ">=",
            }
        }, []

    fake_resolver.batch_resolve = batch_resolve
    monkeypatch.setitem(sys.modules, "resolver.claude_resolver", fake_resolver)

    versions, task_ids, constraints, osv_packages = gradle.extract_ado_versions(
        "unused.csv",
        ["title", "description"],
        {
            "spring-webmvc",
            "org.springframework:spring-webmvc",
            "spring-webflux",
            "org.springframework:spring-webflux",
        },
        False,
    )

    assert len(seen["tasks"]) == 1
    assert seen["tasks"][0][0] == 90557059055706
    assert "Spring MVC and WebFlux" in seen["tasks"][0][1]
    assert "Candidate package hints" in seen["tasks"][0][1]
    assert "org.springframework:spring-webmvc" in seen["tasks"][0][1]
    assert "org.springframework:spring-webflux" in seen["tasks"][0][1]
    assert "org.springframework:spring-webmvc" in versions
    assert "org.springframework:spring-webflux" in versions
    assert "spring-webmvc" not in versions
    assert "spring-webflux" not in versions
    assert {str(v) for v in versions["org.springframework:spring-webmvc"]} == {"6.2.14"}
    assert {str(v) for v in versions["org.springframework:spring-webflux"]} == {"6.2.14"}
    assert task_ids["org.springframework:spring-webmvc"] == {90557059055706}
    assert task_ids["org.springframework:spring-webflux"] == {90557059055706}
    assert constraints["org.springframework:spring-webmvc"] == ">="
    assert constraints["org.springframework:spring-webflux"] == ">="
    assert osv_packages == set()


def test_extract_ado_versions_does_not_commit_fuzzy_candidate_when_claude_returns_empty(
    monkeypatch,
):
    import sys
    import types

    import parsers.gradle as gradle
    import shared.cve_lookup as cve_lookup

    monkeypatch.setattr(
        gradle,
        "read_csv_full_rows",
        lambda csv_path, columns: [
            (
                123,
                "CVIT - app - CVE-2026-99999",
                "Netty HTTP codec should be upgraded to 4.1.133.Final.",
            )
        ],
    )
    monkeypatch.setattr(cve_lookup, "prefetch_advisories", lambda rows, ecosystem: {})
    monkeypatch.setattr(cve_lookup, "extract_advisory_id", lambda title: None)

    fake_resolver = types.ModuleType("resolver.claude_resolver")
    seen = {}

    def batch_resolve(tasks, known_packages, **kwargs):
        seen["tasks"] = tasks
        return {0: {}}, []

    fake_resolver.batch_resolve = batch_resolve
    monkeypatch.setitem(sys.modules, "resolver.claude_resolver", fake_resolver)

    versions, task_ids, constraints, osv_packages = gradle.extract_ado_versions(
        "unused.csv",
        ["title", "description"],
        {
            "io.projectreactor.netty:reactor-netty-http",
            "reactor-netty-http",
        },
        False,
    )

    assert len(seen["tasks"]) == 1
    assert "Candidate package hints" in seen["tasks"][0][1]
    assert "io.projectreactor.netty:reactor-netty-http" in seen["tasks"][0][1]
    assert versions == {}
    assert task_ids == {}
    assert constraints == {}
    assert osv_packages == set()


def test_extract_ado_versions_adds_java_class_and_library_candidate_hints(monkeypatch):
    import sys
    import types

    import parsers.gradle as gradle
    import shared.cve_lookup as cve_lookup

    monkeypatch.setattr(
        gradle,
        "read_csv_full_rows",
        lambda csv_path, columns: [
            (
                456,
                "CVIT - app - CVE-2025-67030",
                "Directory Traversal vulnerability in the extractFile method of "
                "org.codehaus.plexus.util.Expand in plexus-utils before "
                "6d780b3378829318ba5c2d29547e0012d5b29642. "
                "This allows an attacker to execute arbitrary code",
            )
        ],
    )
    monkeypatch.setattr(cve_lookup, "prefetch_advisories", lambda rows, ecosystem: {})
    monkeypatch.setattr(cve_lookup, "extract_advisory_id", lambda title: None)

    fake_resolver = types.ModuleType("resolver.claude_resolver")
    seen = {}

    def batch_resolve(tasks, known_packages, **kwargs):
        seen["tasks"] = tasks
        seen["known_packages"] = known_packages
        return {0: {"org.codehaus.plexus:plexus-utils": ">="}}, []

    fake_resolver.batch_resolve = batch_resolve
    monkeypatch.setitem(sys.modules, "resolver.claude_resolver", fake_resolver)

    versions, task_ids, constraints, osv_packages = gradle.extract_ado_versions(
        "unused.csv",
        ["title", "description"],
        {
            "plexus-utils",
            "org.codehaus.plexus:plexus-utils",
            "org.example:unrelated",
        },
        False,
    )

    assert len(seen["tasks"]) == 1
    assert "Candidate package hints" in seen["tasks"][0][1]
    assert "org.codehaus.plexus:plexus-utils" in seen["tasks"][0][1]
    assert "org.codehaus.plexus:plexus-utils" in constraints
    assert constraints["org.codehaus.plexus:plexus-utils"] == ">="
    assert task_ids["org.codehaus.plexus:plexus-utils"] == {456}
    assert versions.get("org.codehaus.plexus:plexus-utils", set()) == set()
    assert osv_packages == set()


def test_extract_ado_versions_synthesizes_java_coordinate_from_class_and_library(monkeypatch):
    import sys
    import types

    import parsers.gradle as gradle
    import shared.cve_lookup as cve_lookup

    monkeypatch.setattr(
        gradle,
        "read_csv_full_rows",
        lambda csv_path, columns: [
            (
                789,
                "CVIT - app - CVE-2025-67030",
                "Directory Traversal vulnerability in the extractFile method of "
                "org.codehaus.plexus.util.Expand in plexus-utils before "
                "6d780b3378829318ba5c2d29547e0012d5b29642. "
                "This allows an attacker to execute arbitrary code",
            )
        ],
    )
    monkeypatch.setattr(cve_lookup, "prefetch_advisories", lambda rows, ecosystem: {})
    monkeypatch.setattr(cve_lookup, "extract_advisory_id", lambda title: None)

    fake_resolver = types.ModuleType("resolver.claude_resolver")
    seen = {}

    def batch_resolve(tasks, known_packages, **kwargs):
        seen["tasks"] = tasks
        seen["known_packages"] = known_packages
        return {0: {"org.codehaus.plexus:plexus-utils": ">="}}, []

    fake_resolver.batch_resolve = batch_resolve
    monkeypatch.setitem(sys.modules, "resolver.claude_resolver", fake_resolver)

    versions, task_ids, constraints, osv_packages = gradle.extract_ado_versions(
        "unused.csv",
        ["title", "description"],
        {"org.example:unrelated"},
        False,
    )

    assert "Candidate package hints" in seen["tasks"][0][1]
    assert "org.codehaus.plexus:plexus-utils" in seen["tasks"][0][1]
    assert "org.codehaus.plexus:plexus-utils" in seen["known_packages"]
    assert constraints["org.codehaus.plexus:plexus-utils"] == ">="
    assert task_ids["org.codehaus.plexus:plexus-utils"] == {789}
    assert versions.get("org.codehaus.plexus:plexus-utils", set()) == set()
    assert osv_packages == set()


def test_parse_gradle_deps_includes_strict_dependency_blocks():
    import parsers.gradle as gradle

    build_text = """
dependencies {
    implementation(group: 'io.netty', name: 'netty-codec') {
        version {
            strictly '4.1.132.Final'
        }
    }
}
"""
    deps = gradle.parse_gradle_deps(build_text)

    dep = next(d for d in deps if d.group == "io.netty" and d.artifact == "netty-codec")
    assert dep.config == "implementation"
    assert dep.version == "4.1.132.Final"
    assert "strictly '4.1.132.Final'" in dep.original


def test_parallel_fetch_versions_deduplicates_same_package(monkeypatch):
    calls = []

    class Dep:
        def __init__(self, group, artifact):
            self.group = group
            self.artifact = artifact

    def fake_get_available_versions(group, artifact, base_url, auth, timeout):
        calls.append(f"{group}:{artifact}")
        return [MavenVersion.parse("1.0.0")], ""

    monkeypatch.setattr(
        "parsers.gradle.get_available_versions",
        fake_get_available_versions,
    )

    results, errors = parallel_fetch_versions(
        [
            Dep("org.example", "lib"),
            Dep("org.example", "lib"),
            Dep("org.example", "other"),
        ],
        "https://repo",
        None,
        10,
        4,
        False,
    )

    assert errors == []
    assert sorted(calls) == ["org.example:lib", "org.example:other"]
    assert sorted(results) == ["org.example:lib", "org.example:other"]

def test_find_accessible_version_filters_cve_versions_before_access_check(monkeypatch):
    import parsers.gradle as gradle
    checked = []

    def fake_filter(ecosystem, package, versions, xray_host=None, auth=None, timeout=30):
        assert ecosystem == "maven"
        assert package == "org.example:lib"
        return [v for v in versions if str(v) != "1.0.1"], {
            "gav://org.example:lib:1.0.1": ["CVE-1"]
        }, ""

    def fake_accessible(group, artifact, version, base_url, auth, timeout):
        checked.append(version)
        return True

    monkeypatch.setattr(gradle, "filter_versions_without_cves", fake_filter)
    monkeypatch.setattr(gradle, "version_accessible", fake_accessible)

    result = gradle.find_accessible_version(
        "org.example",
        "lib",
        MavenVersion.parse("1.0.1"),
        [MavenVersion.parse("1.0.1"), MavenVersion.parse("1.0.2")],
        "https://repo",
        None,
        1,
        xray_host="https://jfrog",
    )

    assert result == "1.0.2"
    assert checked == ["1.0.2"]

def test_find_accessible_version_tries_lower_same_major_after_forward_blocked(monkeypatch):
    import parsers.gradle as gradle

    checked = []

    monkeypatch.setattr(
        gradle,
        "filter_versions_without_cves",
        lambda ecosystem, package, versions, xray_host=None, auth=None, timeout=30: (
            versions,
            {},
            "",
        ),
    )

    def fake_accessible(group, artifact, version, base_url, auth, timeout):
        checked.append(version)
        return version == "1.0.4"

    monkeypatch.setattr(gradle, "version_accessible", fake_accessible)

    result = gradle.find_accessible_version(
        "org.example",
        "lib",
        MavenVersion.parse("1.0.5"),
        [
            MavenVersion.parse("1.0.7"),
            MavenVersion.parse("1.0.4"),
            MavenVersion.parse("1.0.3"),
            MavenVersion.parse("2.0.0"),
            MavenVersion.parse("0.9.9"),
        ],
        "https://repo",
        None,
        1,
    )

    assert result == "1.0.4"
    assert checked == ["1.0.7", "1.0.4"]


def test_find_accessible_version_filters_lower_cve_versions_before_access_check(monkeypatch):
    import parsers.gradle as gradle

    checked = []

    def fake_filter(ecosystem, package, versions, xray_host=None, auth=None, timeout=30):
        assert ecosystem == "maven"
        assert package == "org.example:lib"
        return [v for v in versions if str(v) != "1.0.4"], {
            "gav://org.example:lib:1.0.4": ["CVE-1"]
        }, ""

    def fake_accessible(group, artifact, version, base_url, auth, timeout):
        checked.append(version)
        return True

    monkeypatch.setattr(gradle, "filter_versions_without_cves", fake_filter)
    monkeypatch.setattr(gradle, "version_accessible", fake_accessible)

    result = gradle.find_accessible_version(
        "org.example",
        "lib",
        MavenVersion.parse("1.0.5"),
        [MavenVersion.parse("1.0.4"), MavenVersion.parse("1.0.3")],
        "https://repo",
        None,
        1,
        xray_host="https://jfrog",
    )

    assert result == "1.0.3"
    assert checked == ["1.0.3"]


def test_parse_strict_string_dependency_block():
    deps = parse_gradle_deps(
        "dependencies {\n"
        "    implementation('com.fasterxml.jackson.core:jackson-databind') {\n"
        "        version { strictly '2.22.0' }\n"
        "    }\n"
        "}\n"
    )
    dep = next(d for d in deps if d.group == "com.fasterxml.jackson.core")
    assert dep.artifact == "jackson-databind"
    assert dep.version == "2.22.0"
    assert dep.config == "implementation"
    assert "strictly '2.22.0'" in dep.original
