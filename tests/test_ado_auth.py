from ado.auth import HTMLTextExtractor, html_to_text, make_headers


class TestHtmlToText:
    def test_empty_string(self):
        assert html_to_text("") == ""

    def test_none_like_input(self):
        assert html_to_text(None) == ""  # type: ignore

    def test_plain_text(self):
        assert html_to_text("hello world") == "hello world"

    def test_strips_tags(self):
        assert html_to_text("<p>hello</p>") == "hello"

    def test_block_tag_br_adds_newline(self):
        result = html_to_text("line1<br>line2")
        assert "line1" in result and "line2" in result

    def test_block_tag_p(self):
        result = html_to_text("<p>para one</p><p>para two</p>")
        assert "para one" in result
        assert "para two" in result

    def test_block_tag_div(self):
        result = html_to_text("<div>section a</div><div>section b</div>")
        assert "section a" in result
        assert "section b" in result

    def test_block_tag_li(self):
        result = html_to_text("<ul><li>item one</li><li>item two</li></ul>")
        assert "item one" in result
        assert "item two" in result

    def test_collapses_multiple_blank_lines(self):
        result = html_to_text("<p>a</p><p></p><p></p><p>b</p>")
        assert "\n\n\n" not in result

    def test_collapses_spaces(self):
        result = html_to_text("hello   world")
        assert "  " not in result

    def test_nested_html(self):
        result = html_to_text("<div><p>text <strong>bold</strong> text</p></div>")
        assert "text" in result
        assert "bold" in result

    def test_strips_result(self):
        result = html_to_text("  <p>content</p>  ")
        assert result == result.strip()


class TestHTMLTextExtractor:
    def test_get_text_basic(self):
        extractor = HTMLTextExtractor()
        extractor.feed("<p>hello</p>")
        assert "hello" in extractor.get_text()

    def test_non_block_tags_ignored(self):
        extractor = HTMLTextExtractor()
        extractor.feed("<span>text</span>")
        assert extractor.get_text() == "text"


class TestMakeHeaders:
    def test_contains_authorization(self):
        headers = make_headers("my-token")
        assert headers["Authorization"] == "Bearer my-token"

    def test_contains_content_type(self):
        headers = make_headers("my-token")
        assert headers["Content-Type"] == "application/json"
