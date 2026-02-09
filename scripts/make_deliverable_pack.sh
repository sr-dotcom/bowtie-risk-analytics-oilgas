#!/usr/bin/env bash
set -euo pipefail

TAG="schema"
SRC_DIR="data/structured/incidents/anthropic"
V23_DIR="data/structured/incidents/schema_v2_3"
RUN_REPORTS_DIR="data/structured/incidents/run_reports"
MANIFEST_CSV="data/structured/structured_manifest.csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    --src) SRC_DIR="$2"; shift 2;;
    --v23) V23_DIR="$2"; shift 2;;
    --run-reports) RUN_REPORTS_DIR="$2"; shift 2;;
    --manifest) MANIFEST_CSV="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 [--tag TAG] [--src DIR] [--v23 DIR] [--run-reports DIR] [--manifest CSV]"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

# --- sanity checks ---
for p in "$SRC_DIR" "$V23_DIR"; do
  [[ -d "$p" ]] || { echo "Missing directory: $p"; exit 1; }
done
[[ -d "$RUN_REPORTS_DIR" ]] || echo "WARN: Missing run reports dir: $RUN_REPORTS_DIR (continuing)"
[[ -f "$MANIFEST_CSV" ]] || echo "WARN: Missing manifest csv: $MANIFEST_CSV (continuing)"

DATE_UTC="$(date -u +%Y-%m-%d)"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"

# count JSON files (best-effort)
V23_COUNT="$(find "$V23_DIR" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')"
SRC_COUNT="$(find "$SRC_DIR" -maxdepth 2 -type f -name '*.json' | wc -l | tr -d ' ')"

DELIVER_BASE="out/deliverables"
NAME="${DATE_UTC}_${TAG}_v2.3_dataset_${V23_COUNT}json_${TS_UTC}"
OUT_DIR="${DELIVER_BASE}/${NAME}"
ZIP_PATH="${DELIVER_BASE}/${NAME}.zip"

mkdir -p "$OUT_DIR"

# Copy data (keep structure predictable for recipients)
mkdir -p "$OUT_DIR/data/structured/incidents"
cp -R "$SRC_DIR" "$OUT_DIR/data/structured/incidents/anthropic"
cp -R "$V23_DIR" "$OUT_DIR/data/structured/incidents/schema_v2_3"

if [[ -d "$RUN_REPORTS_DIR" ]]; then
  cp -R "$RUN_REPORTS_DIR" "$OUT_DIR/data/structured/incidents/run_reports"
fi
if [[ -f "$MANIFEST_CSV" ]]; then
  mkdir -p "$OUT_DIR/data/structured"
  cp "$MANIFEST_CSV" "$OUT_DIR/data/structured/structured_manifest.csv"
fi

# Helpful metadata
cat > "$OUT_DIR/README.md" <<EOF
# Bowtie Risk Analytics — v2.3 Dataset Deliverable

## What this is
This folder contains structured incident extraction outputs and the converted **Schema v2.3** incident JSON set, produced locally (not committed to git).
The \`data/structured/incidents/schema_v2_3/\` folder is a local, gitignored output directory and may be missing in a clean clone.

**Generated (UTC):** ${TS_UTC}
**Tag:** ${TAG}
**Source structured set:** \`${SRC_DIR}\` (**~${SRC_COUNT} JSON**)
**Converted v2.3 set:** \`${V23_DIR}\` (**${V23_COUNT} JSON**)

## Folder layout
- \`data/structured/incidents/anthropic/\`
  - Structured outputs from the LLM extraction step (pre-conversion)
- \`data/structured/incidents/schema_v2_3/\`
  - Converted + normalized **v2.3** incident JSON files
- \`data/structured/incidents/run_reports/\` (if present)
  - Run provenance reports created during extraction
- \`data/structured/structured_manifest.csv\` (if present)
  - Append-only manifest of extraction runs

## Quick verify commands (run from repo root)
1) Generate Schema v2.3 dataset locally (if missing):
\`\`\`bash
python -m src.pipeline convert-schema --incident-dir data/structured/incidents/anthropic --out-dir data/structured/incidents/schema_v2_3
\`\`\`

2) Strict v2.3 schema validation:
\`\`\`bash
python -m src.pipeline schema-check --incident-dir data/structured/incidents/schema_v2_3
\`\`\`

3) Content metrics (informational completeness):
\`\`\`bash
python -m src.pipeline quality-gate --incident-dir data/structured/incidents/schema_v2_3
\`\`\`

## Notes
- Some incidents may legitimately have zero controls (quality-gate will list them as \`no_controls_files\`).
- This dataset is intentionally shared **out-of-band** (Drive/Slack/etc.) to keep the public git repo clean.
EOF

# checksums + counts
(
  cd "$OUT_DIR"
  echo "Generating file inventory + checksums..."
  find . -type f | sort > FILES.txt
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum $(cat FILES.txt) > SHA256SUMS.txt 2>/dev/null || true
  fi
  echo "Counts:" > COUNTS.txt
  echo "  anthropic_json: $(find data/structured/incidents/anthropic -type f -name '*.json' | wc -l | tr -d ' ')" >> COUNTS.txt
  echo "  v23_json:       $(find data/structured/incidents/schema_v2_3 -type f -name '*.json' | wc -l | tr -d ' ')" >> COUNTS.txt
)

# zip it
echo "Creating zip: $ZIP_PATH"
mkdir -p "$DELIVER_BASE"
rm -f "$ZIP_PATH"
( cd "$DELIVER_BASE" && zip -r "$(basename "$ZIP_PATH")" "$(basename "$OUT_DIR")" >/dev/null )

echo ""
echo "Deliverable created:"
echo "  Folder: $OUT_DIR"
echo "  Zip:    $ZIP_PATH"
echo ""
echo "Share the ZIP with your team (Drive/Slack/etc.)."
