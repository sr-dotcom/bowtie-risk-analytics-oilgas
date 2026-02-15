"""Tests for extraction quality gate rules."""
import pytest

from src.extraction.quality_gate import evaluate, compute_metrics


class TestComputeMetrics:
    def test_normal_text(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 20
        m = compute_metrics(text)
        assert m["text_len"] > 400
        assert m["alpha_ratio"] > 0.7
        assert m["cid_ratio"] == 0.0
        assert 0.0 < m["whitespace_ratio"] < 1.0

    def test_empty_text(self) -> None:
        m = compute_metrics("")
        assert m["text_len"] == 0
        assert m["alpha_ratio"] == 0.0
        assert m["cid_ratio"] == 0.0

    def test_cid_text(self) -> None:
        text = "(cid:12)(cid:34)(cid:56)(cid:78)(cid:90) some text here"
        m = compute_metrics(text)
        assert m["cid_ratio"] > 0.0


class TestEvaluate:
    def test_empty_text_fails(self) -> None:
        result = evaluate("")
        assert result.valid is False
        assert result.fail_reason == "EMPTY_TEXT"

    def test_whitespace_only_fails(self) -> None:
        result = evaluate("   \n\t  ")
        assert result.valid is False
        assert result.fail_reason == "EMPTY_TEXT"

    def test_too_short_fails(self) -> None:
        result = evaluate("Short text.")
        assert result.valid is False
        assert result.fail_reason == "TOO_SHORT"

    def test_cid_gibberish_fails(self) -> None:
        cid_text = "(cid:1)(cid:2)(cid:3)(cid:4)(cid:5)" + ("a" * 500)
        result = evaluate(cid_text)
        assert result.valid is False
        assert result.fail_reason == "CID_ENCODING_GIBBERISH"

    def test_low_alpha_fails(self) -> None:
        # Text with lots of digits and symbols, few letters
        garbage = "12345!@#$% " * 100
        result = evaluate(garbage)
        assert result.valid is False
        # Could be TOO_SHORT or LOW_ALPHA_GIBBERISH depending on length
        assert result.fail_reason in ("LOW_ALPHA_GIBBERISH", "TOO_SHORT")

    def test_good_text_passes(self) -> None:
        text = "The chemical release occurred at the refinery on January 15. " * 20
        result = evaluate(text)
        assert result.valid is True
        assert result.fail_reason is None
        assert result.metrics["text_len"] > 400
        assert result.metrics["alpha_ratio"] > 0.55
