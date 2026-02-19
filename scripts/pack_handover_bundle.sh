#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/pack_handover_bundle.sh scan
#   bash scripts/pack_handover_bundle.sh bundle --tag handover_$(date +%Y%m%d_%H%M%S)
#
# What it does:
#  - scan: prints where key artifacts are + counts
#  - bundle: copies a clean minimal handover set into out/handover_<tag>/ and zips it

MODE="${1:-scan}"
shift || true

TAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

ROOT="$(pwd)"
OUTDIR="out"
mkdir -p "$OUTDIR"

echo "Repo root: $ROOT"
echo "Mode: $MODE"
echo

# ---------- Helpers ----------
exists_dir() { [[ -d "$1" ]]; }
exists_file() { [[ -f "$1" ]]; }

find_first_dir() {
  # find_first_dir "data/corpus_v1/structured_json"
  local p="$1"
  if exists_dir "$p"; then
    echo "$p"
    return 0
  fi
  # fallback: search by basename
  local base
  base="$(basename "$p")"
  local hit
  hit="$(find . -type d -name "$base" -print 2>/dev/null | head -n 1 || true)"
  if [[ -n "$hit" ]]; then
    echo "${hit#./}"
  else
    echo ""
  fi
}

find_first_file() {
  # find_first_file "data/processed/controls_combined.csv"
  local p="$1"
  if exists_file "$p"; then
    echo "$p"
    return 0
  fi
  local base
  base="$(basename "$p")"
  local hit
  hit="$(find . -type f -name "$base" -print 2>/dev/null | head -n 1 || true)"
  if [[ -n "$hit" ]]; then
    echo "${hit#./}"
  else
    echo ""
  fi
}

count_json() {
  local dir="$1"
  if [[ -z "$dir" || ! -d "$dir" ]]; then
    echo "0"
    return
  fi
  find "$dir" -maxdepth 1 -type f -name "*.json" | wc -l | tr -d ' '
}

count_csv() {
  local dir="$1"
  if [[ -z "$dir" || ! -d "$dir" ]]; then
    echo "0"
    return
  fi
  find "$dir" -maxdepth 1 -type f -name "*.csv" | wc -l | tr -d ' '
}

# ---------- Locate likely artifacts ----------
CORPUS_JSON_DIR="$(find_first_dir "data/corpus_v1/structured_json")"
CORPUS_MANIFEST="$(find_first_file "data/corpus_v1/manifests/corpus_v1_manifest.csv")"
BSEE_MANIFEST="$(find_first_file "data/raw/bsee/manifest.csv")"
URL_LIST="$(find_first_file "configs/sources/bsee/url_list.csv")"
URL_META="$(find_first_file "configs/sources/bsee/url_list_metadata.csv")"

PROCESSED_DIR="$(find_first_dir "data/processed")"
FLAT_INCIDENTS="$(find_first_file "data/processed/flat_incidents_combined.csv")"
FLAT_INCIDENTS_HF="$(find_first_file "data/processed/flat_incidents_combined_with_hf.csv")"
CONTROLS_CSV="$(find_first_file "data/processed/controls_combined.csv")"

# v2.3 “166 jsons” — we don’t assume path; search common roots
V23_CANDIDATES=()
while IFS= read -r d; do V23_CANDIDATES+=("$d"); done < <(
  find data -type d \( -iname "*schema_v2_3*" -o -iname "*v2_3*" -o -iname "*v2.3*" -o -iname "*schema_v2_3*" \) 2>/dev/null | head -n 20
)
# Also look for directories holding ~166 jsons under data/structured/incidents/*
INCIDENTS_ROOT="$(find_first_dir "data/structured/incidents")"
INCIDENTS_SUBDIRS=()
if [[ -n "$INCIDENTS_ROOT" && -d "$INCIDENTS_ROOT" ]]; then
  while IFS= read -r d; do INCIDENTS_SUBDIRS+=("$d"); done < <(
    find "$INCIDENTS_ROOT" -maxdepth 3 -type d 2>/dev/null
  )
fi

# ---------- SCAN ----------
if [[ "$MODE" == "scan" ]]; then
  echo "=== KEY PATHS (best guess) ==="
  echo "corpus_v1 structured_json dir : ${CORPUS_JSON_DIR:-NOT FOUND}"
  if [[ -n "$CORPUS_JSON_DIR" ]]; then
    echo "  -> JSON count: $(count_json "$CORPUS_JSON_DIR")"
  fi
  echo "corpus_v1 manifest             : ${CORPUS_MANIFEST:-NOT FOUND}"
  echo "bsee ingest manifest           : ${BSEE_MANIFEST:-NOT FOUND}"
  echo "bsee url_list.csv              : ${URL_LIST:-NOT FOUND}"
  echo "bsee url_list_metadata.csv     : ${URL_META:-NOT FOUND}"
  echo
  echo "processed dir                  : ${PROCESSED_DIR:-NOT FOUND}"
  echo "flat_incidents_combined.csv    : ${FLAT_INCIDENTS:-NOT FOUND}"
  echo "flat_incidents_with_hf.csv     : ${FLAT_INCIDENTS_HF:-NOT FOUND}"
  echo "controls_combined.csv          : ${CONTROLS_CSV:-NOT FOUND}"
  echo
  echo "=== POSSIBLE v2.3 / 166-JSON DIRECTORIES (candidates) ==="
  if [[ ${#V23_CANDIDATES[@]} -eq 0 ]]; then
    echo "No obvious schema_v2_3/v2.3 directories found under data/"
  else
    for d in "${V23_CANDIDATES[@]}"; do
      d="${d#./}"
      echo "- $d (json count: $(count_json "$d"))"
    done
  fi
  echo
  echo "=== INCIDENTS DIRECTORIES WITH ~150+ JSONs (auto-detect) ==="
  # Search for directories with 120-300 json files, which likely includes "166 jsons"
  while IFS= read -r line; do
    echo "$line"
  done < <(
    python - <<'PY'
import os
from pathlib import Path

root = Path("data")
hits=[]
for d in root.rglob("*"):
    if d.is_dir():
        try:
            n = sum(1 for _ in d.glob("*.json"))
        except Exception:
            continue
        if 120 <= n <= 300:
            hits.append((n, str(d)))
hits.sort(reverse=True)
for n, d in hits[:40]:
    print(f"- {d} (json count: {n})")
PY
  )
  echo
  echo "Next step:"
  echo "  1) Pick the v2.3 directory from the candidate list above that has ~166 JSONs."
  echo "  2) Run: bash scripts/pack_handover_bundle.sh bundle --tag <your_tag>"
  exit 0
fi

# ---------- BUNDLE ----------
if [[ "$MODE" == "bundle" ]]; then
  if [[ -z "$TAG" ]]; then
    echo "ERROR: bundle mode requires --tag <tag>" >&2
    exit 1
  fi

  BUNDLE_DIR="$OUTDIR/handover_${TAG}"
  rm -rf "$BUNDLE_DIR"
  mkdir -p "$BUNDLE_DIR"

  echo "Creating bundle at: $BUNDLE_DIR"
  echo

  # Copy helper
  copy_if_exists() {
    local src="$1"
    local dest_rel="$2"
    if [[ -z "$src" ]]; then
      echo "SKIP (not found): $dest_rel"
      return
    fi
    if [[ -d "$src" ]]; then
      mkdir -p "$BUNDLE_DIR/$(dirname "$dest_rel")"
      rsync -a --delete "$src/" "$BUNDLE_DIR/$dest_rel/"
      echo "OK   dir : $src -> $dest_rel/"
    elif [[ -f "$src" ]]; then
      mkdir -p "$BUNDLE_DIR/$(dirname "$dest_rel")"
      cp -p "$src" "$BUNDLE_DIR/$dest_rel"
      echo "OK  file : $src -> $dest_rel"
    else
      echo "SKIP (missing): $src"
    fi
  }

  # Core deliverables (corpus_v1 line)
  copy_if_exists "$FLAT_INCIDENTS" "data/processed/flat_incidents_combined.csv"
  copy_if_exists "$FLAT_INCIDENTS_HF" "data/processed/flat_incidents_combined_with_hf.csv"
  copy_if_exists "$CONTROLS_CSV" "data/processed/controls_combined.csv"
  copy_if_exists "$BSEE_MANIFEST" "data/raw/bsee/manifest.csv"
  copy_if_exists "$CORPUS_MANIFEST" "data/corpus_v1/manifests/corpus_v1_manifest.csv"
  copy_if_exists "$URL_LIST" "configs/sources/bsee/url_list.csv"
  copy_if_exists "$URL_META" "configs/sources/bsee/url_list_metadata.csv"
  copy_if_exists "$CORPUS_JSON_DIR" "data/corpus_v1/structured_json"

  # Minimal code context for reproducibility
  copy_if_exists "src" "src"
  copy_if_exists "scripts" "scripts"
  copy_if_exists "pyproject.toml" "pyproject.toml"
  copy_if_exists "requirements.txt" "requirements.txt"
  copy_if_exists "README.md" "README.md"
  copy_if_exists "DEVLOG.md" "DEVLOG.md"

  # Create index files
  (cd "$BUNDLE_DIR" && find . -type f | sort > FILE_INDEX.txt)
  echo "Wrote FILE_INDEX.txt"

  # Create zip
  ZIP_PATH="${BUNDLE_DIR}.zip"
  rm -f "$ZIP_PATH"
  (cd "$OUTDIR" && zip -r "handover_${TAG}.zip" "handover_${TAG}" >/dev/null)
  echo "Created zip: $ZIP_PATH"
  echo
  echo "Done."
  echo "Now you can upload the zip (or just FILE_INDEX.txt first) here."
  exit 0
fi

echo "Unknown mode: $MODE (use scan or bundle)" >&2
exit 1