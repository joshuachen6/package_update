from shared.maven_version import MAVEN_VERSION_RE, MavenVersion


class TestMavenVersionParse:
    def test_basic_three_part(self):
        v = MavenVersion.parse("1.2.3")
        assert v is not None
        assert v.major == 1 and v.minor == 2 and v.patch == 3 and v.build == 0
        assert v.raw == "1.2.3"

    def test_two_part(self):
        v = MavenVersion.parse("5.3")
        assert v is not None
        assert v.major == 5 and v.minor == 3 and v.patch == 0 and v.build == 0

    def test_four_part(self):
        v = MavenVersion.parse("1.2.3.4")
        assert v is not None
        assert v.major == 1 and v.minor == 2 and v.patch == 3 and v.build == 4

    def test_release_qualifier(self):
        v = MavenVersion.parse("5.3.27.RELEASE")
        assert v is not None
        assert v.major == 5 and v.minor == 3 and v.patch == 27 and v.build == 0

    def test_snapshot_qualifier(self):
        v = MavenVersion.parse("2.1.0-SNAPSHOT")
        assert v is not None
        assert v.major == 2 and v.minor == 1 and v.patch == 0

    def test_hyphen_qualifier(self):
        v = MavenVersion.parse("3.0.0-M1")
        assert v is not None
        assert v.major == 3

    def test_empty_returns_none(self):
        assert MavenVersion.parse("") is None

    def test_none_like_returns_none(self):
        assert MavenVersion.parse("not-valid") is None

    def test_str_returns_raw(self):
        v = MavenVersion.parse("5.3.27.RELEASE")
        assert str(v) == "5.3.27.RELEASE"


class TestMavenVersionComparison:
    def test_lt_patch(self):
        assert MavenVersion.parse("1.0.0") < MavenVersion.parse("1.0.1")

    def test_lt_minor(self):
        assert MavenVersion.parse("1.0.9") < MavenVersion.parse("1.1.0")

    def test_lt_major(self):
        assert MavenVersion.parse("1.9.9") < MavenVersion.parse("2.0.0")

    def test_lt_build(self):
        assert MavenVersion.parse("1.0.0.0") < MavenVersion.parse("1.0.0.1")

    def test_le(self):
        a = MavenVersion.parse("1.2.3")
        assert a <= MavenVersion.parse("1.2.3")
        assert a <= MavenVersion.parse("1.2.4")

    def test_gt(self):
        assert MavenVersion.parse("2.0.0") > MavenVersion.parse("1.9.9")

    def test_ge(self):
        a = MavenVersion.parse("1.2.3")
        assert a >= MavenVersion.parse("1.2.3")
        assert a >= MavenVersion.parse("1.2.2")

    def test_equality(self):
        assert MavenVersion.parse("1.2.3") == MavenVersion.parse("1.2.3")

    def test_qualifier_ignored_in_comparison(self):
        # Qualifier is ignored in ordering; neither is less than the other (same numeric rank)
        a = MavenVersion.parse("5.3.27.RELEASE")
        b = MavenVersion.parse("5.3.27")
        assert not (a < b) and not (b < a)

    def test_sorted(self):
        versions = [MavenVersion.parse(v) for v in ["3.0.0", "1.0.0", "2.0.0"]]
        assert sorted(versions) == [
            MavenVersion.parse("1.0.0"),
            MavenVersion.parse("2.0.0"),
            MavenVersion.parse("3.0.0"),
        ]

    def test_max(self):
        versions = [MavenVersion.parse(v) for v in ["1.0.0", "1.9.0", "1.2.0"]]
        assert max(versions) == MavenVersion.parse("1.9.0")


class TestMavenVersionRegex:
    def test_finds_version_in_text(self):
        matches = MAVEN_VERSION_RE.findall("upgrade from 1.2.3 to 1.4.0")
        assert "1.2.3" in matches
        assert "1.4.0" in matches

    def test_finds_with_qualifier(self):
        matches = MAVEN_VERSION_RE.findall("use spring 5.3.27.RELEASE")
        assert "5.3.27.RELEASE" in matches

    def test_no_match_inside_word(self):
        # word-boundary guard: version inside an identifier shouldn't match
        assert not MAVEN_VERSION_RE.search("abc1.2.3def")

    def test_no_match_single_number(self):
        assert not MAVEN_VERSION_RE.search("version 5")


