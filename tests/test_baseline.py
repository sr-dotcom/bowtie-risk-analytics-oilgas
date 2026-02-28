import json
import pytest
import tempfile
from pathlib import Path
import pandas as pd

from src.analytics.baseline import (
    barrier_status_distribution,
    failure_rates,
    co_occurrence_crosstab,
    human_contribution_summary,
    run_baseline,
    load_controls,
)


def _make_controls_df() -> pd.DataFrame:
    """Create a sample controls DataFrame."""
    return pd.DataFrame([
        {
            "incident_id": "INC-001", "control_id": "C-001", "name": "Gas detector",
            "side": "prevention", "barrier_role": "detect", "barrier_type": "engineering",
            "line_of_defense": "1st", "barrier_status": "active",
            "barrier_failed": False, "human_contribution_value": None,
            "barrier_failed_human": False, "confidence": "high", "supporting_text_count": 2,
        },
        {
            "incident_id": "INC-001", "control_id": "C-002", "name": "ESD valve",
            "side": "prevention", "barrier_role": "isolate", "barrier_type": "engineering",
            "line_of_defense": "2nd", "barrier_status": "failed",
            "barrier_failed": True, "human_contribution_value": "operator_error",
            "barrier_failed_human": True, "confidence": "medium", "supporting_text_count": 1,
        },
        {
            "incident_id": "INC-001", "control_id": "C-003", "name": "Fire suppression",
            "side": "mitigation", "barrier_role": "control", "barrier_type": "engineering",
            "line_of_defense": "3rd", "barrier_status": "failed",
            "barrier_failed": True, "human_contribution_value": None,
            "barrier_failed_human": False, "confidence": "low", "supporting_text_count": 0,
        },
    ])


class TestBarrierStatusDistribution:
    def test_counts_and_percentages(self):
        df = _make_controls_df()
        result = barrier_status_distribution(df)
        assert result["active"]["count"] == 1
        assert result["failed"]["count"] == 2
        assert abs(result["active"]["pct"] - 1/3) < 0.01


class TestFailureRates:
    def test_by_barrier_type(self):
        df = _make_controls_df()
        result = failure_rates(df, "barrier_type")
        assert "engineering" in result
        eng = result["engineering"]
        assert eng["total"] == 3
        assert eng["failed"] == 2

    def test_by_side(self):
        df = _make_controls_df()
        result = failure_rates(df, "side")
        assert "prevention" in result
        assert "mitigation" in result

    def test_missing_column(self):
        df = _make_controls_df()
        result = failure_rates(df, "nonexistent_col")
        assert result == {}


class TestCoOccurrenceCrosstab:
    def test_co_occurring_failures(self):
        df = _make_controls_df()
        result = co_occurrence_crosstab(df)
        # C-002 (ESD valve) and C-003 (Fire suppression) both failed in INC-001
        assert len(result) == 1
        assert result.iloc[0]["co_occurrences"] == 1

    def test_no_failures(self):
        df = _make_controls_df()
        df["barrier_failed"] = False
        result = co_occurrence_crosstab(df)
        assert result.empty


class TestHumanContribution:
    def test_summary(self):
        df = _make_controls_df()
        result = human_contribution_summary(df)
        assert result["total_controls"] == 3
        assert result["human_contribution_mentioned"] == 1
        assert result["barrier_failed_human_count"] == 1


class TestRunBaseline:
    def test_produces_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "derived"
            csv_path = Path(tmpdir) / "controls.csv"

            df = _make_controls_df()
            df.to_csv(csv_path, index=False)

            run_baseline(csv_path, out_dir)

            assert (out_dir / "control_summary.json").exists()
            assert (out_dir / "failure_crosstab.csv").exists()

            summary = json.loads((out_dir / "control_summary.json").read_text())
            assert summary["total_controls"] == 3
            assert summary["total_incidents"] == 1

    def test_missing_csv_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                load_controls(Path(tmpdir) / "nonexistent.csv")
