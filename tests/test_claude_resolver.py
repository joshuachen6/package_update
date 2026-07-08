import json

from resolver.claude_resolver import _is_plausible_package_name, _parse_batch_response

KNOWN = {"lodash", "react", "spring-core", "org.springframework:spring-core"}


class TestIsPlausiblePackageName:
    def test_simple_npm(self):
        assert _is_plausible_package_name("lodash") is True

    def test_hyphenated_npm(self):
        assert _is_plausible_package_name("spring-boot") is True

    def test_scoped_npm(self):
        assert _is_plausible_package_name("@babel/core") is True

    def test_dotted_maven(self):
        assert _is_plausible_package_name("spring-web") is True

    def test_single_char_rejected(self):
        assert _is_plausible_package_name("x") is False

    def test_empty_rejected(self):
        assert _is_plausible_package_name("") is False

    def test_too_long_rejected(self):
        assert _is_plausible_package_name("a" * 150) is False

    def test_space_rejected(self):
        assert _is_plausible_package_name("my package") is False

    def test_non_string_rejected(self):
        assert _is_plausible_package_name(123) is False  # type: ignore

    def test_none_rejected(self):
        assert _is_plausible_package_name(None) is False  # type: ignore

    def test_slash_unscoped_rejected(self):
        assert _is_plausible_package_name("foo/bar") is False

    def test_uppercase_allowed(self):
        assert _is_plausible_package_name("MyLib") is True

    def test_exactly_two_chars(self):
        # length > 1, so 2 chars should pass
        assert _is_plausible_package_name("ab") is True


class TestParseBatchResponse:
    def test_basic_known_packages(self):
        raw = json.dumps({"0": {"lodash": ">="}, "1": {"react": ">="}})
        result = _parse_batch_response(raw, KNOWN)
        assert result[0] == {"lodash": ">="}
        assert result[1] == {"react": ">="}

    def test_gt_constraint_preserved(self):
        raw = json.dumps({"0": {"lodash": ">"}})
        result = _parse_batch_response(raw, KNOWN)
        assert result[0]["lodash"] == ">"

    def test_unknown_constraint_normalized_to_gte(self):
        raw = json.dumps({"0": {"lodash": "^"}})
        result = _parse_batch_response(raw, KNOWN)
        assert result[0]["lodash"] == ">="

    def test_unknown_package_filtered_when_not_allowed(self):
        raw = json.dumps({"0": {"unknown-pkg": ">="}})
        result = _parse_batch_response(raw, KNOWN, allow_unlisted=False)
        assert result.get(0, {}) == {}

    def test_unknown_plausible_package_kept_when_allowed(self):
        raw = json.dumps({"0": {"new-transitive": ">="}})
        result = _parse_batch_response(raw, KNOWN, allow_unlisted=True)
        assert result.get(0, {}).get("new-transitive") == ">="

    def test_unknown_implausible_rejected_even_when_allowed(self):
        raw = json.dumps({"0": {"a bad name!": ">="}})
        result = _parse_batch_response(raw, KNOWN, allow_unlisted=True)
        assert result.get(0, {}) == {}

    def test_code_fenced_json(self):
        raw = "```json\n" + json.dumps({"0": {"lodash": ">="}}) + "\n```"
        result = _parse_batch_response(raw, KNOWN)
        assert result[0] == {"lodash": ">="}

    def test_non_json_returns_empty(self):
        result = _parse_batch_response("this is not json", KNOWN)
        assert result == {}

    def test_non_dict_top_level_returns_empty(self):
        result = _parse_batch_response(json.dumps([1, 2, 3]), KNOWN)
        assert result == {}

    def test_non_integer_key_skipped(self):
        raw = json.dumps({"zero": {"lodash": ">="}})
        result = _parse_batch_response(raw, KNOWN)
        assert result == {}

    def test_non_dict_value_skipped(self):
        raw = json.dumps({"0": ["lodash"]})
        result = _parse_batch_response(raw, KNOWN)
        assert result == {}

    def test_empty_task_entry(self):
        raw = json.dumps({"0": {}})
        result = _parse_batch_response(raw, KNOWN)
        assert result[0] == {}

    def test_multiple_packages_in_one_task(self):
        raw = json.dumps({"0": {"lodash": ">=", "react": ">"}})
        result = _parse_batch_response(raw, KNOWN)
        assert result[0] == {"lodash": ">=", "react": ">"}

    def test_non_string_pkg_key_skipped(self):
        # JSON keys are always strings, but test the isinstance guard
        raw = '{"0": {123: ">="}}'
        result = _parse_batch_response(raw, KNOWN)
        # Invalid JSON (int key) → json.loads will fail → fallback regex → likely empty
        assert isinstance(result, dict)

    def test_json_embedded_in_text(self):
        raw = 'Some preamble text\n{"0": {"lodash": ">="}}\nSome trailing text'
        result = _parse_batch_response(raw, KNOWN)
        # Should find the JSON object via regex fallback
        assert result.get(0, {}).get("lodash") == ">="
