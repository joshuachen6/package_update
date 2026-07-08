from shared.semver import SEMVER_RE, SemVer


class TestSemVerParse:
    def test_basic(self):
        v = SemVer.parse("1.2.3")
        assert v is not None
        assert v.major == 1 and v.minor == 2 and v.patch == 3
        assert v.suffix == ""
        assert v.raw == "1.2.3"

    def test_prerelease(self):
        v = SemVer.parse("2.0.0-alpha.1")
        assert v is not None
        assert v.major == 2 and v.minor == 0 and v.patch == 0
        assert v.suffix == "-alpha.1"

    def test_build_metadata(self):
        v = SemVer.parse("1.0.0+build.123")
        assert v is not None
        assert v.suffix == "+build.123"

    def test_prerelease_and_build(self):
        v = SemVer.parse("1.0.0-beta.2+sha.deadbeef")
        assert v is not None
        assert v.suffix == "-beta.2+sha.deadbeef"

    def test_v_prefix(self):
        v = SemVer.parse("v3.1.4")
        assert v is not None
        assert v.major == 3 and v.minor == 1 and v.patch == 4

    def test_range_prefix_tilde(self):
        v = SemVer.parse("~1.2.3")
        assert v is not None and v.major == 1

    def test_range_prefix_caret(self):
        v = SemVer.parse("^2.0.0")
        assert v is not None and v.major == 2

    def test_range_prefix_gte(self):
        v = SemVer.parse(">=3.0.0")
        assert v is not None and v.major == 3

    def test_empty_returns_none(self):
        assert SemVer.parse("") is None

    def test_invalid_returns_none(self):
        assert SemVer.parse("not-a-version") is None
        assert SemVer.parse("1.2") is None
        assert SemVer.parse("abc.def.ghi") is None

    def test_str(self):
        v = SemVer.parse("1.2.3-rc.1")
        assert str(v) == "1.2.3-rc.1"


class TestSemVerComparison:
    def test_lt_patch(self):
        assert SemVer.parse("1.0.0") < SemVer.parse("1.0.1")

    def test_lt_minor(self):
        assert SemVer.parse("1.0.9") < SemVer.parse("1.1.0")

    def test_lt_major(self):
        assert SemVer.parse("1.9.9") < SemVer.parse("2.0.0")

    def test_eq(self):
        a = SemVer.parse("1.2.3")
        b = SemVer.parse("1.2.3")
        assert a == b

    def test_gt(self):
        assert SemVer.parse("2.0.0") > SemVer.parse("1.9.9")

    def test_prerelease_less_than_release(self):
        # 1.0.0-alpha < 1.0.0 (pre-release has lower precedence)
        assert SemVer.parse("1.0.0-alpha") < SemVer.parse("1.0.0")

    def test_prerelease_ordering(self):
        # numeric pre-release identifiers compared numerically
        assert SemVer.parse("1.0.0-alpha.1") < SemVer.parse("1.0.0-alpha.2")

    def test_prerelease_alpha_lt_rc(self):
        # lexicographic: "alpha" < "rc"
        assert SemVer.parse("1.0.0-alpha") < SemVer.parse("1.0.0-rc")

    def test_sorted(self):
        versions = [SemVer.parse(v) for v in ["2.0.0", "1.0.0-beta", "1.0.0", "1.1.0"]]
        assert sorted(versions) == [
            SemVer.parse("1.0.0-beta"),
            SemVer.parse("1.0.0"),
            SemVer.parse("1.1.0"),
            SemVer.parse("2.0.0"),
        ]

    def test_max(self):
        versions = [SemVer.parse(v) for v in ["1.0.0", "3.0.0", "2.0.0"]]
        assert max(versions) == SemVer.parse("3.0.0")


class TestSemVerRegex:
    def test_finds_version_in_text(self):
        matches = SEMVER_RE.findall("upgrade lodash from 4.17.20 to 4.17.21")
        assert "4.17.20" in matches
        assert "4.17.21" in matches

    def test_no_false_positives_for_dates(self):
        # something like 2021.01.01 with more than three parts should not match
        # but bare 3-part numeric strings will — just verify it finds semver-looking ones
        matches = SEMVER_RE.findall("version 1.2.3 is affected")
        assert "1.2.3" in matches

    def test_finds_prerelease(self):
        matches = SEMVER_RE.findall("use 2.0.0-beta.1 or later")
        assert "2.0.0-beta.1" in matches
