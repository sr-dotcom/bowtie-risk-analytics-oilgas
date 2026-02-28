"""Deterministic extraction quality gate with tunable thresholds."""
import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------
MIN_TEXT_LEN: int = 400
MAX_CID_RATIO: float = 0.01
MAX_CID_COUNT: int = 5
MIN_ALPHA_RATIO: float = 0.55

_CID_PATTERN = re.compile(r"\(cid:\d+\)")


@dataclass
class QualityResult:
    """Result of quality gate evaluation."""

    valid: bool
    fail_reason: Optional[str]
    metrics: dict = field(default_factory=dict)


def compute_metrics(text: str) -> dict:
    """Compute text quality metrics."""
    text_len = len(text)
    if text_len == 0:
        return {
            "text_len": 0,
            "alpha_ratio": 0.0,
            "cid_ratio": 0.0,
            "whitespace_ratio": 0.0,
            "cid_count": 0,
        }

    alpha_count = sum(1 for c in text if c.isalpha())
    whitespace_count = sum(1 for c in text if c.isspace())
    cid_matches = _CID_PATTERN.findall(text)
    cid_char_count = sum(len(m) for m in cid_matches)

    return {
        "text_len": text_len,
        "alpha_ratio": round(alpha_count / text_len, 4),
        "cid_ratio": round(cid_char_count / text_len, 4),
        "whitespace_ratio": round(whitespace_count / text_len, 4),
        "cid_count": len(cid_matches),
    }


def evaluate(text: str) -> QualityResult:
    """Apply quality gate rules to extracted text.

    Rules checked in order (first failure wins):
    1. EMPTY_TEXT — empty or whitespace-only
    2. TOO_SHORT — text_len < MIN_TEXT_LEN
    3. CID_ENCODING_GIBBERISH — cid_ratio > MAX_CID_RATIO or cid_count >= MAX_CID_COUNT
    4. LOW_ALPHA_GIBBERISH — alpha_ratio < MIN_ALPHA_RATIO
    """
    stripped = text.strip()
    metrics = compute_metrics(stripped)

    if len(stripped) == 0:
        return QualityResult(valid=False, fail_reason="EMPTY_TEXT", metrics=metrics)

    if metrics["text_len"] < MIN_TEXT_LEN:
        return QualityResult(valid=False, fail_reason="TOO_SHORT", metrics=metrics)

    if metrics["cid_ratio"] > MAX_CID_RATIO or metrics["cid_count"] >= MAX_CID_COUNT:
        return QualityResult(
            valid=False, fail_reason="CID_ENCODING_GIBBERISH", metrics=metrics
        )

    if metrics["alpha_ratio"] < MIN_ALPHA_RATIO:
        return QualityResult(
            valid=False, fail_reason="LOW_ALPHA_GIBBERISH", metrics=metrics
        )

    return QualityResult(valid=True, fail_reason=None, metrics=metrics)
