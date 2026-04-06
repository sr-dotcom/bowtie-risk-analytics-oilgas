"""Generate apriori_rules.json from normalized barrier co-failure data.

Reads the normalized barrier CSV produced by the association mining scripts,
filters to failed barriers, groups by incident to form transactions, and
computes pairwise co-occurrence rules using pure Python (itertools.combinations
+ collections.Counter).  No mlxtend dependency required.

Algorithm
---------
1. Load ``out/association_mining/normalized_df.csv``.
2. Filter to failed barriers: ``barrier_status in
   ('failed', 'degraded', 'not_installed', 'bypassed')``.
3. Group by ``incident_id``, collect a **set** of unique ``barrier_family``
   values per incident → transactions list.
4. Count individual family appearances (``family_counts``) and pair
   co-appearances (``pair_counts``) via ``itertools.combinations(sorted(fam), 2)``.
5. For each pair (A, B) compute both directions A→B and B→A:

   - ``support    = pair_count / n_incidents``
   - ``confidence = pair_count / family_count[antecedent]``
   - ``lift       = confidence / (family_count[consequent] / n_incidents)``

6. Retain rules where ``support >= 0.05``, ``confidence >= 0.5``, ``lift > 1.0``.
7. Sort by confidence descending.
8. Write JSON artifact to ``data/models/artifacts/apriori_rules.json``.

``n_incidents`` is the number of incidents that contain *at least one* failed
barrier (i.e. ``len(transactions)``), which is the natural population for
association rule mining over co-failure patterns.

Usage::

    python scripts/generate_apriori_rules.py

Writes ``data/models/artifacts/apriori_rules.json``.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
INPUT_CSV = Path("out/association_mining/normalized_df.csv")
ARTIFACTS_DIR = Path("data/models/artifacts")
OUTPUT_PATH = ARTIFACTS_DIR / "apriori_rules.json"

# ---------------------------------------------------------------------------
# Hyper-parameters
# ---------------------------------------------------------------------------
FAILED_STATUSES: frozenset[str] = frozenset(
    {"failed", "degraded", "not_installed", "bypassed"}
)
MIN_SUPPORT: float = 0.05
MIN_CONFIDENCE: float = 0.5
MIN_LIFT: float = 1.0


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_normalized_csv(path: Path) -> pd.DataFrame:
    """Load the normalized barrier CSV.

    Args:
        path: Path to ``normalized_df.csv``.

    Returns:
        DataFrame with at minimum the columns
        ``incident_id``, ``barrier_family``, and ``barrier_status``.

    Raises:
        FileNotFoundError: If the file does not exist.
        KeyError: If required columns are missing.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Normalized barrier CSV not found at {path}. "
            "Run: python scripts/association_mining/event_barrier_normalization.py"
        )
    df = pd.read_csv(path)
    required = {"incident_id", "barrier_family", "barrier_status"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns in {path}: {missing}")
    logger.info("Loaded %d rows from %s", len(df), path)
    return df


def build_transactions(df: pd.DataFrame) -> tuple[dict[str, set[str]], int]:
    """Filter to failed barriers and build per-incident transaction sets.

    Args:
        df: Full normalized barrier DataFrame.

    Returns:
        Tuple of (transactions dict mapping incident_id → set of barrier families,
        n_incidents used as the population denominator).

    ``n_incidents`` equals the number of incidents with at least one failed
    barrier, which is the natural denominator for co-failure association rules.
    """
    df_failed = df[df["barrier_status"].isin(FAILED_STATUSES)].copy()
    logger.info(
        "Rows after failure filter: %d / %d (statuses: %s)",
        len(df_failed),
        len(df),
        ", ".join(sorted(FAILED_STATUSES)),
    )

    transactions: dict[str, set[str]] = (
        df_failed.groupby("incident_id")["barrier_family"]
        .apply(set)
        .to_dict()
    )
    n_incidents = len(transactions)
    logger.info(
        "Transactions (incidents with ≥1 failed barrier): %d", n_incidents
    )
    return transactions, n_incidents


def compute_counts(
    transactions: dict[str, set[str]],
) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    """Count individual family appearances and pair co-appearances.

    Args:
        transactions: Mapping of incident_id → set of barrier_family values.

    Returns:
        Tuple of (family_counts, pair_counts).
        ``pair_counts`` keys are lexicographically-sorted (a, b) pairs so each
        unordered pair is counted once.
    """
    family_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()

    for families in transactions.values():
        family_counts.update(families)
        for pair in combinations(sorted(families), 2):
            pair_counts[pair] += 1

    logger.info(
        "Unique barrier families in failed transactions: %d",
        len(family_counts),
    )
    logger.info("Unique co-occurrence pairs: %d", len(pair_counts))
    return family_counts, pair_counts


def generate_rules(
    family_counts: Counter[str],
    pair_counts: Counter[tuple[str, str]],
    n_incidents: int,
    min_support: float = MIN_SUPPORT,
    min_confidence: float = MIN_CONFIDENCE,
    min_lift: float = MIN_LIFT,
) -> list[dict[str, object]]:
    """Derive association rules from co-occurrence counts.

    For each unordered pair (A, B) with sufficient support, both directions
    A→B and B→A are evaluated.

    Args:
        family_counts: Per-family appearance counts across transactions.
        pair_counts: Pair co-occurrence counts (sorted-key tuples).
        n_incidents: Total incident count used as population denominator.
        min_support: Minimum support threshold (default 0.05).
        min_confidence: Minimum confidence threshold (default 0.5).
        min_lift: Minimum lift threshold, exclusive (default 1.0).

    Returns:
        List of rule dicts sorted by confidence descending, each with keys:
        ``antecedent``, ``consequent``, ``support``, ``confidence``,
        ``lift``, ``count``.
    """
    rules: list[dict[str, object]] = []

    for (a, b), cnt in pair_counts.items():
        support = cnt / n_incidents
        if support < min_support:
            continue

        for antecedent, consequent in [(a, b), (b, a)]:
            confidence = cnt / family_counts[antecedent]
            lift = confidence / (family_counts[consequent] / n_incidents)
            if confidence >= min_confidence and lift > min_lift:
                rules.append(
                    {
                        "antecedent": antecedent,
                        "consequent": consequent,
                        "support": round(support, 6),
                        "confidence": round(confidence, 6),
                        "lift": round(lift, 6),
                        "count": cnt,
                    }
                )

    rules.sort(key=lambda r: -r["confidence"])  # type: ignore[arg-type]
    logger.info(
        "Rules after thresholds (support≥%.2f, conf≥%.2f, lift>%.1f): %d",
        min_support,
        min_confidence,
        min_lift,
        len(rules),
    )
    return rules


def write_artifact(
    rules: list[dict[str, object]],
    n_incidents: int,
    output_path: Path,
    min_support: float = MIN_SUPPORT,
    min_confidence: float = MIN_CONFIDENCE,
    min_lift: float = MIN_LIFT,
) -> None:
    """Write the rules artifact JSON to disk.

    Args:
        rules: List of rule dicts.
        n_incidents: Population denominator recorded in metadata.
        output_path: Destination path.
        min_support: Recorded in metadata.
        min_confidence: Recorded in metadata.
        min_lift: Recorded in metadata.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "rules": rules,
        "metadata": {
            "n_incidents": n_incidents,
            "min_support": min_support,
            "min_confidence": min_confidence,
            "min_lift": min_lift,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        },
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    logger.info("Written to %s (%d rules)", output_path, len(rules))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate apriori_rules.json from normalized barrier co-failure data."""
    logger.info("=== generate_apriori_rules.py ===")

    df = load_normalized_csv(INPUT_CSV)
    transactions, n_incidents = build_transactions(df)

    family_counts, pair_counts = compute_counts(transactions)
    rules = generate_rules(family_counts, pair_counts, n_incidents)

    write_artifact(rules, n_incidents, OUTPUT_PATH)

    print(
        f"OK: {len(rules)} rules written to {OUTPUT_PATH} "
        f"(n_incidents={n_incidents})"
    )


if __name__ == "__main__":
    main()
