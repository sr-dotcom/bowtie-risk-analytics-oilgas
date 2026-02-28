"""Tests for text normalization."""
import pytest

from src.extraction.normalize import normalize_text


class TestNormalizeText:
    def test_nbsp_replaced(self) -> None:
        assert normalize_text("hello\u00a0world") == "hello world"

    def test_smart_quotes_replaced(self) -> None:
        text = "\u201cHello\u201d \u2018world\u2019"
        result = normalize_text(text)
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert "\u2018" not in result
        assert "\u2019" not in result
        assert '"Hello"' in result
        assert "'world'" in result

    def test_control_chars_removed(self) -> None:
        text = "hello\x00\x01\x02world"
        result = normalize_text(text)
        assert "\x00" not in result
        assert "helloworld" in result

    def test_preserves_newlines_and_tabs(self) -> None:
        text = "line1\nline2\ttab"
        result = normalize_text(text)
        assert "\n" in result
        assert "\t" in result

    def test_collapses_excessive_whitespace(self) -> None:
        text = "hello     world"
        result = normalize_text(text)
        assert "     " not in result
        assert "hello" in result
        assert "world" in result

    def test_strips_line_whitespace(self) -> None:
        text = "  hello  \n  world  "
        result = normalize_text(text)
        assert result == "hello\nworld"

    def test_preserves_paragraphs(self) -> None:
        text = "Paragraph one.\n\nParagraph two."
        result = normalize_text(text)
        assert "\n\n" in result

    def test_empty_input(self) -> None:
        assert normalize_text("") == ""

    def test_em_dash_and_en_dash(self) -> None:
        text = "hello\u2014world\u2013again"
        result = normalize_text(text)
        assert "hello" in result and "world" in result
