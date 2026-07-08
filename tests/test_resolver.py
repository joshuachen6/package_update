from resolver.resolver import highest_ado_criteria_by_major, select_best_version
from shared.maven_version import MavenVersion
from shared.semver import SemVer


def sv(*versions):
    return {SemVer.parse(v) for v in versions}


def mv(*versions):
    return {MavenVersion.parse(v) for v in versions}


def svlist(*versions):
    return [SemVer.parse(v) for v in versions]


def mvlist(*versions):
    return [MavenVersion.parse(v) for v in versions]


class TestSelectBestVersionSemVer:
    def test_no_ado_versions_returns_none(self):
        result = select_best_version(set(), svlist("1.0.0", "1.1.0"), major=1)
        assert result is None

    def test_no_matching_major_returns_none(self):
        # ADO mentions major 2, but we ask for major 1
        result = select_best_version(sv("2.0.0"), svlist("1.0.0", "1.1.0"), major=1)
        assert result is None

    def test_exact_match_preferred(self):
        # ADO mentions 1.2.3 and it's in available → return it
        result = select_best_version(sv("1.2.3"), svlist("1.2.3", "1.3.0"), major=1)
        assert result == SemVer.parse("1.2.3")

    def test_exact_highest_ado_preferred(self):
        # ADO mentions both 1.2.3 and 1.3.0, both available → return highest (1.3.0)
        result = select_best_version(
            sv("1.2.3", "1.3.0"), svlist("1.2.3", "1.3.0", "1.4.0"), major=1
        )
        assert result == SemVer.parse("1.3.0")

    def test_fallback_to_highest_available_gte(self):
        # ADO mentions 1.2.3 but not in available; fallback picks highest available >= 1.2.3
        result = select_best_version(sv("1.2.3"), svlist("1.2.0", "1.4.0", "1.5.0"), major=1)
        assert result == SemVer.parse("1.5.0")

    def test_no_available_gte_returns_none(self):
        # ADO minimum is 1.5.0 but all available are lower
        result = select_best_version(sv("1.5.0"), svlist("1.0.0", "1.2.0"), major=1)
        assert result is None

    def test_constraint_gt_picks_strictly_above(self):
        # constraint ">" means the ADO version itself is bad; need strictly above
        result = select_best_version(
            sv("1.2.3"), svlist("1.2.3", "1.2.4", "1.3.0"), major=1, constraint=">"
        )
        # exact would require v > 1.2.3 AND in ado_for_major — impossible since min==1.2.3
        # fallback: highest available > 1.2.3 with same major
        assert result == SemVer.parse("1.3.0")

    def test_constraint_gt_excludes_minimum(self):
        # With ">" constraint, 1.2.3 itself must not be returned
        result = select_best_version(sv("1.2.3"), svlist("1.2.3"), major=1, constraint=">")
        assert result is None

    def test_default_constraint_is_gte(self):
        # minimum itself should be acceptable with default ">="
        result = select_best_version(sv("1.2.3"), svlist("1.2.3"), major=1)
        assert result == SemVer.parse("1.2.3")

    def test_cross_major_ignored(self):
        # available has major 2 versions; those should be excluded when major=1 is requested
        result = select_best_version(sv("1.2.3"), svlist("1.2.3", "2.0.0"), major=1)
        assert result == SemVer.parse("1.2.3")


class TestSelectBestVersionMaven:
    def test_basic_maven(self):
        result = select_best_version(mv("5.3.10"), mvlist("5.3.10", "5.3.27"), major=5)
        assert result == MavenVersion.parse("5.3.10")

    def test_fallback_maven(self):
        result = select_best_version(mv("5.3.10"), mvlist("5.3.20", "5.3.27"), major=5)
        assert result == MavenVersion.parse("5.3.27")

    def test_maven_constraint_gt(self):
        result = select_best_version(
            mv("5.3.10"), mvlist("5.3.10", "5.3.11"), major=5, constraint=">"
        )
        assert result == MavenVersion.parse("5.3.11")


class TestHighestAdoCriteriaByMajor:
    def test_single_package_single_version(self):
        result = highest_ado_criteria_by_major({"lodash": sv("4.17.21")})
        assert result == {"lodash": {4: SemVer.parse("4.17.21")}}

    def test_picks_highest_per_major(self):
        result = highest_ado_criteria_by_major({"lodash": sv("4.17.20", "4.17.21")})
        assert result["lodash"][4] == SemVer.parse("4.17.21")

    def test_multiple_majors(self):
        result = highest_ado_criteria_by_major({"react": sv("16.14.0", "17.0.2", "18.0.0")})
        assert result["react"][16] == SemVer.parse("16.14.0")
        assert result["react"][17] == SemVer.parse("17.0.2")
        assert result["react"][18] == SemVer.parse("18.0.0")

    def test_multiple_packages(self):
        result = highest_ado_criteria_by_major(
            {
                "lodash": sv("4.17.21"),
                "react": sv("18.0.0"),
            }
        )
        assert 4 in result["lodash"]
        assert 18 in result["react"]

    def test_empty_input(self):
        assert highest_ado_criteria_by_major({}) == {}

    def test_empty_versions_for_package(self):
        result = highest_ado_criteria_by_major({"lodash": set()})
        assert result.get("lodash", {}) == {}


def test_select_best_version_prefers_current_minor_when_ado_mentions_it():
    from resolver.resolver import select_best_version
    from shared.maven_version import MavenVersion

    def mv(raw):
        parsed = MavenVersion.parse(raw)
        assert parsed is not None
        return parsed

    current = mv("4.1.132.Final")
    ado = {mv("4.1.133.Final"), mv("4.2.0.Final"), mv("4.2.13.Final")}
    available = [mv("4.1.133.Final"), mv("4.1.135.Final"), mv("4.2.13.Final")]
    assert str(select_best_version(ado, available, current.major, ">=", current)) == "4.1.133.Final"


def test_select_best_version_allows_new_minor_when_current_minor_not_in_ado():
    from resolver.resolver import select_best_version
    from shared.maven_version import MavenVersion

    def mv(raw):
        parsed = MavenVersion.parse(raw)
        assert parsed is not None
        return parsed

    current = mv("4.1.132.Final")
    ado = {mv("4.2.0.Final"), mv("4.2.13.Final")}
    available = [mv("4.1.135.Final"), mv("4.2.13.Final")]

    assert str(select_best_version(ado, available, current.major, ">=", current)) == "4.2.13.Final"


def test_select_best_version_never_crosses_current_major():
    from resolver.resolver import select_best_version
    from shared.maven_version import MavenVersion

    def mv(raw):
        parsed = MavenVersion.parse(raw)
        assert parsed is not None
        return parsed

    current = mv("4.1.132.Final")
    ado = {mv("5.0.0.Final")}
    available = [mv("4.1.135.Final"), mv("5.0.0.Final")]

    assert select_best_version(ado, available, current.major, ">=", current) is None
