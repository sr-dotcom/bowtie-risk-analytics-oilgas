"""End-to-end smoke test for the GroupKFold(5) mini-gate.

Marked @pytest.mark.slow — skipped unless -m slow is passed or the
parquet is explicitly present.  Also skipped when the parquet is absent
so CI can run without needing the data file.
"""

import pathlib
import pytest

_PARQUET = pathlib.Path("data/processed/cascading_training.parquet")
_REPORT = pathlib.Path("data/models/evaluation/cascading_mini_gate_report.md")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not _PARQUET.exists(),
        reason="data/processed/cascading_training.parquet not present",
    ),
]


def test_mini_gate_auc_passes():
    """Mean GroupKFold(5) AUC on y_fail_target must be ≥ 0.70."""
    from src.modeling.cascading.mini_gate import run_mini_gate

    fold_aucs, mean_auc, std_auc, passed = run_mini_gate(
        parquet_path=_PARQUET,
        report_path=_REPORT,
    )

    assert len(fold_aucs) == 5, f"Expected 5 fold AUCs, got {len(fold_aucs)}"
    assert mean_auc >= 0.70, (
        f"Mean AUC {mean_auc:.4f} below gate threshold 0.70; "
        f"per-fold: {[f'{a:.4f}' for a in fold_aucs]}"
    )
    assert passed, "Gate returned passed=False despite mean AUC ≥ 0.70"


def test_mini_gate_report_written():
    """Report file must exist and contain 'Verdict: PASS' after gate runs."""
    from src.modeling.cascading.mini_gate import run_mini_gate

    run_mini_gate(parquet_path=_PARQUET, report_path=_REPORT)

    assert _REPORT.exists(), f"Report not written to {_REPORT}"
    content = _REPORT.read_text(encoding="utf-8")
    assert "Verdict: PASS" in content, (
        f"'Verdict: PASS' not found in report:\n{content}"
    )


def test_mini_gate_report_has_five_folds():
    """Report must have exactly 5 fold rows in the AUC table."""
    from src.modeling.cascading.mini_gate import run_mini_gate

    run_mini_gate(parquet_path=_PARQUET, report_path=_REPORT)

    content = _REPORT.read_text(encoding="utf-8")
    fold_lines = [
        ln for ln in content.splitlines()
        if ln.startswith("| ") and ln.strip().endswith("|") and "Fold" not in ln and "---" not in ln
    ]
    assert len(fold_lines) == 5, (
        f"Expected 5 fold rows in report, found {len(fold_lines)}"
    )
