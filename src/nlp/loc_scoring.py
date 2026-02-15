"""Keyword-based Loss of Containment (LOC) scoring for CSB reports."""

import csv
import re
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Keyword groups
# ---------------------------------------------------------------------------

PRIMARY_LOC_TERMS: list[str] = [
    "release",
    "spill",
    "leak",
    "loss of containment",
    "discharge",
    "escape",
    "rupture",
    "blowout",
]

SECONDARY_LOC_TERMS: list[str] = [
    "explosion",
    "fire",
]

HAZARDOUS_CONTEXT: list[str] = [
    "chemical",
    "ammonia",
    "gas",
    "vapor",
    "hydrogen",
    "oil",
    "refinery",
    "toxic",
    "explosion",
    "fire",
]

# Pre-compile patterns (word-boundary, case-insensitive)
_PRIMARY_PATTERNS = [(t, re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE)) for t in PRIMARY_LOC_TERMS]
_SECONDARY_PATTERNS = [(t, re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE)) for t in SECONDARY_LOC_TERMS]
_HAZARDOUS_PATTERNS = [(t, re.compile(rf"\b{re.escape(t)}\b", re.IGNORECASE)) for t in HAZARDOUS_CONTEXT]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "data" / "raw" / "csb" / "manifest.csv"
CSB_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "csb"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "csb_loc_scored.csv"


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _count_matches(text: str, patterns: list[tuple[str, re.Pattern]]) -> tuple[int, list[str]]:
    """Return total match count and list of matched terms."""
    total = 0
    matched: list[str] = []
    for term, pat in patterns:
        count = len(pat.findall(text))
        if count > 0:
            total += count
            matched.append(term)
    return total, matched


def score_text(text: str) -> dict:
    """Score a single document's text for LOC relevance."""
    primary_count, matched_primary = _count_matches(text, _PRIMARY_PATTERNS)
    secondary_count, matched_secondary = _count_matches(text, _SECONDARY_PATTERNS)
    hazardous_count, matched_context = _count_matches(text, _HAZARDOUS_PATTERNS)

    loc_score = (primary_count * 2) + (secondary_count * 1) + hazardous_count
    loc_flag = (primary_count >= 1 and hazardous_count >= 1) or (secondary_count >= 1 and hazardous_count >= 2)

    return {
        "loc_score": loc_score,
        "primary_count": primary_count,
        "secondary_count": secondary_count,
        "hazardous_count": hazardous_count,
        "loc_flag": loc_flag,
        "text_length": len(text),
        "matched_primary_terms": "|".join(matched_primary),
        "matched_secondary_terms": "|".join(matched_secondary),
        "matched_context_terms": "|".join(matched_context),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> pd.DataFrame:
    """Load CSB manifest, score each document, and save results."""
    if not MANIFEST_PATH.exists():
        print(f"ERROR: Manifest not found at {MANIFEST_PATH}")
        sys.exit(1)

    # Read manifest
    rows: list[dict] = []
    with open(MANIFEST_PATH, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("ERROR: Manifest is empty.")
        sys.exit(1)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    print(f"Manifest loaded: {len(rows)} total rows, {len(ok_rows)} with status=ok")

    results: list[dict] = []
    for row in ok_rows:
        doc_id = row["doc_id"]
        text_path = CSB_RAW_DIR / row["text_path"]

        if not text_path.exists():
            print(f"  WARN: text file missing for {doc_id}: {text_path}")
            continue

        text = text_path.read_text(encoding="utf-8", errors="replace")
        scores = score_text(text)
        scores["doc_id"] = doc_id
        scores["url"] = row.get("url", "")
        results.append(scores)

    if not results:
        print("ERROR: No documents could be scored.")
        sys.exit(1)

    # Build DataFrame with desired column order
    df = pd.DataFrame(results)
    df = df[
        [
            "doc_id",
            "url",
            "loc_score",
            "primary_count",
            "secondary_count",
            "hazardous_count",
            "loc_flag",
            "text_length",
            "matched_primary_terms",
            "matched_secondary_terms",
            "matched_context_terms",
        ]
    ]
    df = df.sort_values("loc_score", ascending=False).reset_index(drop=True)

    # Ensure output directory exists and save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nResults saved to {OUTPUT_PATH}")

    # ---- Summary stats ----
    total = len(df)
    flagged = int(df["loc_flag"].sum())
    pct = (flagged / total * 100) if total else 0.0

    print("\n===== LOC Scoring Summary =====")
    print(f"  Total documents processed : {total}")
    print(f"  Total LOC flagged         : {flagged}")
    print(f"  Percentage LOC            : {pct:.1f}%")
    print("\n  Top 5 highest loc_score:")
    top5 = df.head(5)
    for _, r in top5.iterrows():
        print(f"    {r['doc_id']:50s}  score={r['loc_score']}")

    return df


def run_with_extraction_manifest(
    manifest_path: Path,
    text_dir: Path,
    output_path: Path,
) -> pd.DataFrame:
    """Score LOC using extraction manifest — skip EXTRACTION_FAILED documents.

    Documents with extraction_status != OK get final_label=EXTRACTION_FAILED
    and are not scored. Only OK documents are LOC-scored.

    Args:
        manifest_path: Path to extraction_manifest.csv.
        text_dir: Directory containing normalized text files.
        output_path: Path to write scored CSV.

    Returns:
        DataFrame with all rows including scored and failed.
    """
    manifest_df = pd.read_csv(manifest_path, dtype=str)

    results: list[dict] = []

    for _, row in manifest_df.iterrows():
        doc_id = row["doc_id"]
        extraction_status = row.get("extraction_status", "OK")
        fail_reason = row.get("fail_reason", "")

        if extraction_status != "OK":
            results.append({
                "doc_id": doc_id,
                "final_label": "EXTRACTION_FAILED",
                "loc_score": None,
                "primary_count": None,
                "secondary_count": None,
                "hazardous_count": None,
                "loc_flag": None,
                "extraction_status": extraction_status,
                "fail_reason": fail_reason if fail_reason else None,
                "extractor_used": row.get("extractor_used", ""),
                "text_len": row.get("text_len", "0"),
                "matched_primary_terms": "",
                "matched_secondary_terms": "",
                "matched_context_terms": "",
            })
            continue

        # Read text file
        text_path = text_dir / row.get("text_path", f"{doc_id}.txt")
        if not text_path.exists():
            results.append({
                "doc_id": doc_id,
                "final_label": "EXTRACTION_FAILED",
                "loc_score": None,
                "primary_count": None,
                "secondary_count": None,
                "hazardous_count": None,
                "loc_flag": None,
                "extraction_status": "EXTRACTION_FAILED",
                "fail_reason": "TEXT_FILE_MISSING",
                "extractor_used": row.get("extractor_used", ""),
                "text_len": "0",
                "matched_primary_terms": "",
                "matched_secondary_terms": "",
                "matched_context_terms": "",
            })
            continue

        text = text_path.read_text(encoding="utf-8", errors="replace")
        scores = score_text(text)

        loc_flag = scores["loc_flag"]
        final_label = "TRUE" if loc_flag else "FALSE"

        results.append({
            "doc_id": doc_id,
            "final_label": final_label,
            "loc_score": scores["loc_score"],
            "primary_count": scores["primary_count"],
            "secondary_count": scores["secondary_count"],
            "hazardous_count": scores["hazardous_count"],
            "loc_flag": loc_flag,
            "extraction_status": "OK",
            "fail_reason": None,
            "extractor_used": row.get("extractor_used", ""),
            "text_len": scores["text_length"],
            "matched_primary_terms": scores["matched_primary_terms"],
            "matched_secondary_terms": scores["matched_secondary_terms"],
            "matched_context_terms": scores["matched_context_terms"],
        })

    df = pd.DataFrame(results)

    col_order = [
        "doc_id", "final_label", "loc_score", "primary_count", "secondary_count",
        "hazardous_count", "loc_flag", "extraction_status", "fail_reason",
        "extractor_used", "text_len", "matched_primary_terms",
        "matched_secondary_terms", "matched_context_terms",
    ]
    df = df[[c for c in col_order if c in df.columns]]

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    # Print summary
    total = len(df)
    ok_scored = len(df[df["final_label"].isin(["TRUE", "FALSE"])])
    true_count = len(df[df["final_label"] == "TRUE"])
    false_count = len(df[df["final_label"] == "FALSE"])
    failed = len(df[df["final_label"] == "EXTRACTION_FAILED"])

    print(f"\n===== LOC Scoring Summary =====")
    print(f"  Total documents      : {total}")
    print(f"  OK scored            : {ok_scored} (TRUE={true_count}, FALSE={false_count})")
    print(f"  EXTRACTION_FAILED    : {failed}")

    if failed > 0:
        fail_reasons = df[df["final_label"] == "EXTRACTION_FAILED"]["fail_reason"].value_counts()
        for reason, count in fail_reasons.items():
            print(f"    {reason}: {count}")

    return df


if __name__ == "__main__":
    run()
