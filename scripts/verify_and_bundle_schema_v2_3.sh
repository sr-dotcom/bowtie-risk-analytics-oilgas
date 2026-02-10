#!/usr/bin/env bash
set -euo pipefail

TAG="schema"
SRC_DIR="data/structured/incidents/anthropic"
OUT_DIR="data/structured/incidents/schema_v2_3"
RUN_REPORTS_DIR="data/structured/incidents/run_reports"
MANIFEST_CSV="data/structured/structured_manifest.csv"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    --src) SRC_DIR="$2"; shift 2;;
    --out) OUT_DIR="$2"; shift 2;;
    --run-reports) RUN_REPORTS_DIR="$2"; shift 2;;
    --manifest) MANIFEST_CSV="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 [--tag TAG] [--src DIR] [--out DIR] [--run-reports DIR] [--manifest CSV]"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

REPO_ROOT="$(pwd)"
DATE_UTC="$(date -u +%Y-%m-%d)"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"

echo "=== Repo sanity checks ==="
[[ -f "scripts/make_deliverable_pack.sh" ]] || { echo "ERROR: scripts/make_deliverable_pack.sh not found"; exit 1; }
[[ -d "$SRC_DIR" ]] || { echo "ERROR: Missing source directory: $SRC_DIR"; exit 1; }

echo "OK: Found SRC_DIR=$SRC_DIR"
echo "Target OUT_DIR=$OUT_DIR"

echo ""
echo "=== Count current files (best-effort) ==="
SRC_COUNT="$(find "$SRC_DIR" -type f -name '*.json' | wc -l | tr -d ' ')"
OUT_COUNT="0"
if [[ -d "$OUT_DIR" ]]; then
  OUT_COUNT="$(find "$OUT_DIR" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')"
fi
echo "anthropic_json_count=$SRC_COUNT"
echo "schema_v2_3_json_count=$OUT_COUNT"

echo ""
echo "=== Ensure Schema v2.3 dataset exists locally ==="
if [[ ! -d "$OUT_DIR" ]] || [[ "$OUT_COUNT" -eq 0 ]]; then
  echo "Schema v2.3 output dir missing/empty. Generating via convert-schema..."
  python -m src.pipeline convert-schema \
    --incident-dir "$SRC_DIR" \
    --out-dir "$OUT_DIR"
else
  echo "Schema v2.3 output dir exists and has JSON. Skipping convert-schema."
fi

OUT_COUNT="$(find "$OUT_DIR" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ')"
echo "schema_v2_3_json_count=$OUT_COUNT"

echo ""
echo "=== Validations ==="
python -m src.pipeline schema-check --incident-dir "$OUT_DIR"
python -m src.pipeline quality-gate --incident-dir "$OUT_DIR"
pytest -q

echo ""
echo "=== Build deliverable ZIP ==="
bash scripts/make_deliverable_pack.sh --tag "$TAG" --src "$SRC_DIR" --v23 "$OUT_DIR" --run-reports "$RUN_REPORTS_DIR" --manifest "$MANIFEST_CSV"

# Find the newest deliverable folder/zip (most recent by name)
DELIVER_BASE="out/deliverables"
LATEST_ZIP="$(ls -1t "$DELIVER_BASE"/*.zip | head -n 1 || true)"
LATEST_DIR_NAME="$(basename "${LATEST_ZIP%.zip}")"
LATEST_DIR="$DELIVER_BASE/$LATEST_DIR_NAME"

if [[ -z "${LATEST_ZIP:-}" ]] || [[ ! -d "$LATEST_DIR" ]]; then
  echo "ERROR: Could not locate newly created deliverable under $DELIVER_BASE"
  exit 1
fi

echo ""
echo "=== Add: top-level inventory + README additions (inside deliverable folder only) ==="
(
  cd "$LATEST_DIR"

  # Create an inventory of key paths & counts
  cat > BUNDLE_INVENTORY.md <<EOF
# Deliverable Inventory (Schema v2.3)

**Generated (UTC):** ${TS_UTC}  
**Repo root (local):** ${REPO_ROOT}

## What’s included
### 1) Source structured outputs (pre-normalization)
- **Path:** \`data/structured/incidents/anthropic/\`
- **What:** Raw structured extraction outputs from the LLM extraction step
- **Files:** $(find data/structured/incidents/anthropic -type f -name '*.json' | wc -l | tr -d ' ')

### 2) Normalized Schema v2.3 outputs
- **Path:** \`data/structured/incidents/jeffrey_v2_3/\` OR \`data/structured/incidents/schema_v2_3/\`
- **What:** Normalized incident JSON files in **Schema v2.3** format

> NOTE: If your pack script copies to a fixed folder name, check the folder listing below.
EOF

  # Detect which folder name exists inside the deliverable
  if [[ -d "data/structured/incidents/schema_v2_3" ]]; then
    V23_PATH="data/structured/incidents/schema_v2_3"
  elif [[ -d "data/structured/incidents/jeffrey_v2_3" ]]; then
    # backward-compat if any older pack uses this name
    V23_PATH="data/structured/incidents/jeffrey_v2_3"
  else
    V23_PATH="(not found)"
  fi

  cat >> BUNDLE_INVENTORY.md <<EOF

- **Detected v2.3 folder:** \`${V23_PATH}\`
- **Files:** $( [[ "$V23_PATH" != "(not found)" ]] && find "$V23_PATH" -maxdepth 1 -type f -name '*.json' | wc -l | tr -d ' ' || echo "0" )

### 3) Run provenance (optional)
- **Path:** \`data/structured/incidents/run_reports/\` (if present)
- **What:** Provenance / run metadata from extraction runs

### 4) Manifest (optional)
- **Path:** \`data/structured/structured_manifest.csv\` (if present)
- **What:** Append-only manifest of extraction runs

## Quick verification commands (run from repo root)
1) Validate Schema v2.3 JSON:
\`\`\`bash
python -m src.pipeline schema-check --incident-dir ${OUT_DIR}
\`\`\`

2) Completeness metrics:
\`\`\`bash
python -m src.pipeline quality-gate --incident-dir ${OUT_DIR}
\`\`\`

3) Tests:
\`\`\`bash
pytest -q
\`\`\`

## Folder listing (deliverable)
\`\`\`
$(find data -maxdepth 5 -type d | sort)
\`\`\`
EOF

  # Add a simple FILES list too
  find . -type f | sort > FILES.txt
)

echo ""
echo "✅ Bundle complete:"
echo "  Deliverable folder: $LATEST_DIR"
echo "  Deliverable zip:    $LATEST_ZIP"
echo ""
echo "Inside the deliverable folder, see:"
echo "  - README.md"
echo "  - BUNDLE_INVENTORY.md"
echo "  - FILES.txt"
