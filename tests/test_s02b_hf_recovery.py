"""S02b tests: y_hf_fail signal recovery experiment + D016 branch activation.

Asserts (a) both variant CV reports exist and are populated, (b) the recovery
report contains exactly one regex-matchable Activated branch line, (c) the
y_hf_fail metadata ``s02b_branch`` key matches the report, (d) the joblib
artifact was replaced iff branch in {A, B}, and (e) the y_fail pipeline +
metadata remain byte-identical to their S02 completion state.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_ARTIFACTS = Path("data/models/artifacts")
_EVAL = Path("data/models/evaluation")

# Frozen S02-completion sha256 fingerprints — captured pre-S02b.
# Any Branch C run MUST leave y_hf_fail pipeline byte-identical to this.
# Any run MUST leave y_fail pipeline+metadata byte-identical to these.
PRE_S02B_Y_HF_FAIL_PIPELINE_SHA256 = (
    "29afd5c493fae2d238e838b8bf61d81b03d53b3831d0a7dec8362a0bc17e9209"
)
PRE_S02B_Y_FAIL_PIPELINE_SHA256 = (
    "fdaaf689e772caff22c652ff6bc3bb59f8b9e960ac80b9bd27f8ed79cfea63bd"
)
PRE_S02B_Y_FAIL_METADATA_SHA256 = (
    "d52c116eef635283c0618ee9afb6a26402eacb7170691cbe42a18d3c0d99d34c"
)

_ACTIVATED_RE = re.compile(r"^Activated branch: [ABC]$", re.MULTILINE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _branch_from_report() -> str:
    text = _read(_EVAL / "s02b_hf_recovery_report.md")
    matches = _ACTIVATED_RE.findall(text)
    assert len(matches) == 1, (
        f"Expected exactly 1 'Activated branch' line, got {len(matches)}"
    )
    return matches[0].split(":", 1)[1].strip()


# (a) Both variant CV reports exist and contain Mean AUC + per-fold table
def test_variant_reports_exist_and_populated():
    for fname in ("s02b_variant_A_cv.md", "s02b_variant_B_cv.md"):
        path = _EVAL / fname
        assert path.exists(), f"{fname} missing"
        text = _read(path)
        assert "Mean AUC" in text, f"{fname} lacks 'Mean AUC'"
        assert "per-fold" in text.lower(), f"{fname} lacks per-fold section"


# (b) Recovery report exists with exactly one regex-matchable branch line
def test_recovery_report_has_single_branch_line():
    path = _EVAL / "s02b_hf_recovery_report.md"
    assert path.exists(), "s02b_hf_recovery_report.md missing"
    text = _read(path)
    matches = _ACTIVATED_RE.findall(text)
    assert len(matches) == 1, (
        f"Expected exactly one Activated branch line, got {len(matches)}"
    )


# (c) Metadata s02b_branch matches report
def test_metadata_s02b_branch_matches_report():
    branch = _branch_from_report()
    meta = json.loads(_read(_ARTIFACTS / "xgb_cascade_y_hf_fail_metadata.json"))
    assert meta.get("s02b_branch") == branch, (
        f"metadata s02b_branch={meta.get('s02b_branch')!r} "
        f"!= report branch={branch!r}"
    )


# (d) Artifact replacement iff branch in {A, B}
def test_artifact_replacement_matches_branch():
    branch = _branch_from_report()
    current = _sha256(_ARTIFACTS / "xgb_cascade_y_hf_fail_pipeline.joblib")
    if branch in ("A", "B"):
        assert current != PRE_S02B_Y_HF_FAIL_PIPELINE_SHA256, (
            f"Branch {branch} requires pipeline replacement; "
            f"sha256 unchanged: {current}"
        )
    else:
        assert current == PRE_S02B_Y_HF_FAIL_PIPELINE_SHA256, (
            f"Branch C requires byte-identical pipeline; "
            f"sha256 changed: {current}"
        )
        # Branch C must include the s02b_note annotation.
        meta = json.loads(
            _read(_ARTIFACTS / "xgb_cascade_y_hf_fail_metadata.json")
        )
        assert "s02b_note" in meta, (
            "Branch C metadata must include s02b_note annotation"
        )


# (e) y_fail pipeline + metadata unchanged from S02 completion
def test_y_fail_artifacts_unchanged():
    pipe_sha = _sha256(_ARTIFACTS / "xgb_cascade_y_fail_pipeline.joblib")
    meta_sha = _sha256(_ARTIFACTS / "xgb_cascade_y_fail_metadata.json")
    assert pipe_sha == PRE_S02B_Y_FAIL_PIPELINE_SHA256, (
        f"y_fail pipeline drifted from S02 completion: {pipe_sha}"
    )
    assert meta_sha == PRE_S02B_Y_FAIL_METADATA_SHA256, (
        f"y_fail metadata drifted from S02 completion: {meta_sha}"
    )
