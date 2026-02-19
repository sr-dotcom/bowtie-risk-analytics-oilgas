from pathlib import Path
import pandas as pd

from src.analytics.control_coverage_v0 import compute_coverage_and_gaps_from_flat


def test_compute_coverage_and_gaps_from_flat(tmp_path: Path):
    # Minimal flat controls CSV fixture
    df = pd.DataFrame([
        # incident A: 2 controls (active + degraded)
        {"incident_id": "A", "control_id": "C1", "name": "ctrl1", "barrier_status": "active", "supporting_text_count": 2, "confidence": "high"},
        {"incident_id": "A", "control_id": "C2", "name": "ctrl2", "barrier_status": "degraded", "supporting_text_count": 1, "confidence": "medium"},
        # incident B: 2 controls (failed + blank status, no evidence)
        {"incident_id": "B", "control_id": "C3", "name": "ctrl3", "barrier_status": "failed", "supporting_text_count": 0, "confidence": "high"},
        {"incident_id": "B", "control_id": "C4", "name": "ctrl4", "barrier_status": "", "supporting_text_count": 0, "confidence": ""},
    ])

    flat = tmp_path / "flat.csv"
    out_dir = tmp_path / "out"
    df.to_csv(flat, index=False)

    # Fake structured_dir universe so reindex keeps A and B
    structured_dir = tmp_path / "structured_json"
    structured_dir.mkdir()
    (structured_dir / "A.json").write_text("{}", encoding="utf-8")
    (structured_dir / "B.json").write_text("{}", encoding="utf-8")

    outs = compute_coverage_and_gaps_from_flat(flat, out_dir, structured_dir=structured_dir)

    cov = pd.read_csv(outs.coverage_csv)
    gaps = pd.read_csv(outs.gaps_csv)
    rollups = pd.read_csv(outs.rollups_csv)

    # Coverage score: A = (1 + 0.5*1)/2 = 0.75 ; B = (0 + 0)/2 = 0.0
    a = cov[cov["incident_id"] == "A"].iloc[0]
    b = cov[cov["incident_id"] == "B"].iloc[0]
    assert abs(a["coverage_score_v0"] - 0.75) < 1e-9
    assert abs(b["coverage_score_v0"] - 0.0) < 1e-9

    # Gaps should include both B controls and not include A controls
    assert set(gaps["incident_id"].unique().tolist()) == {"B"}
    assert len(gaps) == 2

    # Rollups should be tidy
    assert set(rollups.columns) == {"rollup", "dimension", "value", "gap_count"}
    assert len(rollups) > 0
