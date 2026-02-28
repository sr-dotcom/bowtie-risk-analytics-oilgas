"""Baseline analytics on flattened controls dataset."""
import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_controls(csv_path: Path) -> pd.DataFrame:
    """Load flattened controls CSV into DataFrame."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Controls CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    # Convert boolean-like columns
    for col in ["barrier_failed", "barrier_failed_human"]:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df


def barrier_status_distribution(df: pd.DataFrame) -> dict:
    """Count and percentage of each barrier_status value."""
    counts = df["barrier_status"].value_counts()
    total = len(df)
    return {
        status: {"count": int(count), "pct": round(count / total, 4) if total > 0 else 0.0}
        for status, count in counts.items()
    }


def failure_rates(df: pd.DataFrame, group_col: str) -> dict:
    """Failure rate (barrier_failed=True proportion) grouped by a column."""
    if group_col not in df.columns:
        return {}
    grouped = df.groupby(group_col)["barrier_failed"].agg(["sum", "count"])
    grouped["rate"] = grouped["sum"] / grouped["count"]
    return {
        idx: {"failed": int(row["sum"]), "total": int(row["count"]), "rate": round(row["rate"], 4)}
        for idx, row in grouped.iterrows()
    }


def co_occurrence_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    """Crosstab of control names that co-occur as failed within the same incident."""
    failed = df[df["barrier_failed"] == True][["incident_id", "name"]]
    if failed.empty:
        return pd.DataFrame()

    # Self-join on incident_id to find co-occurring failures
    merged = failed.merge(failed, on="incident_id", suffixes=("_a", "_b"))
    # Remove self-pairs and duplicates
    merged = merged[merged["name_a"] < merged["name_b"]]

    if merged.empty:
        return pd.DataFrame()

    crosstab = merged.groupby(["name_a", "name_b"]).size().reset_index(name="co_occurrences")
    return crosstab


def human_contribution_summary(df: pd.DataFrame) -> dict:
    """Summary statistics for human contribution and human-caused failures."""
    total = len(df)
    human_mentioned = df["human_contribution_value"].notna().sum()
    human_failed = df["barrier_failed_human"].sum() if "barrier_failed_human" in df.columns else 0

    return {
        "total_controls": int(total),
        "human_contribution_mentioned": int(human_mentioned),
        "human_contribution_pct": round(human_mentioned / total, 4) if total > 0 else 0.0,
        "barrier_failed_human_count": int(human_failed),
        "barrier_failed_human_pct": round(human_failed / total, 4) if total > 0 else 0.0,
    }


def run_baseline(controls_csv: Path, out_dir: Path) -> None:
    """Run all baseline analyses and write outputs.

    Outputs:
        - out_dir/control_summary.json: status distribution, failure rates, human summary
        - out_dir/failure_crosstab.csv: co-occurrence of failures
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_controls(controls_csv)
    logger.info(f"Loaded {len(df)} control rows from {controls_csv}")

    summary = {
        "total_controls": len(df),
        "total_incidents": int(df["incident_id"].nunique()),
        "barrier_status_distribution": barrier_status_distribution(df),
        "failure_rate_by_barrier_type": failure_rates(df, "barrier_type"),
        "failure_rate_by_side": failure_rates(df, "side"),
        "failure_rate_by_line_of_defense": failure_rates(df, "line_of_defense"),
        "human_contribution": human_contribution_summary(df),
    }

    summary_path = out_dir / "control_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(f"Wrote control summary to {summary_path}")

    crosstab = co_occurrence_crosstab(df)
    crosstab_path = out_dir / "failure_crosstab.csv"
    if not crosstab.empty:
        crosstab.to_csv(crosstab_path, index=False)
        logger.info(f"Wrote failure crosstab ({len(crosstab)} pairs) to {crosstab_path}")
    else:
        # Write empty CSV with headers
        crosstab_path.write_text("name_a,name_b,co_occurrences\n", encoding="utf-8")
        logger.info(f"No co-occurring failures found, wrote empty crosstab to {crosstab_path}")
