# corpus_v1 Design

**Date:** 2026-02-18
**Status:** Approved — proceeding to implementation

---

## Goal

Build a clean evaluation corpus of ~150 real agency incident report PDFs with exactly one Claude-extracted structured JSON per PDF, in Jeffrey v2.3 schema.

---

## Corpus Definition

- **One PDF → one structured JSON.** No multi-provider outputs.
- **Claude (Anthropic) only.** Existing anthropic bucket JSONs are reused; all fresh extractions use Claude.
- **Real incident reports only.** No CSB Status_Change_Summary docs, policy docs, safety studies, sample stubs, or canary sets.

---

## Directory Layout

```
data/corpus_v1/
  raw_pdfs/               ← 148 PDFs (100 BSEE + 48 CSB), flat
  structured_json/        ← 1 JSON per PDF, Claude-only, V2.3 schema
  structured_json_noise/  ← JSONs that have no matching PDF (quarantined)
  manifests/
    corpus_v1_manifest.csv
```

---

## Corpus Composition

| Source | PDFs | JSON status |
|--------|------|-------------|
| BSEE (`bsee/pdfs/`) | 100 | 100 existing anthropic JSONs → copy + convert to V2.3 |
| CSB (`csb/pdf/`, filtered) | 48 | 0 JSONs → extract fresh with Claude |
| **Total** | **148** | 100 ready, 48 pending |

**CSB PDFs excluded (non-incident):**
- `csb-safety-study-remote-isolation-of-process-equipment.pdf`
- `key-lessons-for-preventing-incidents-from-flammable-chemicals-in-educational-dem.pdf`

---

## Noise Exclusion Rules

**Noise JSONs** (in `structured_json/`, no matching PDF in `raw_pdfs/`) — move to `structured_json_noise/`:
- All `Status_Change_Summary_*` files (CSB recommendation-tracking docs)
- `CSB_Gas_Purging_Urgent_Recommendations_*.json`
- `SCS2.json`, `FinalDataQualityGuidelines_*.json`, `Urgent_Recommendations_*.json`
- `sample_incident_*.json`, `sample_incidents.json`
- `bayer_report_final.json`

**Rule:** Any JSON in `structured_json/` whose URL-decoded stem does not match any PDF stem in `raw_pdfs/` is noise.

---

## Canonical JSON Selection (deterministic)

For each PDF stem `S`:
1. `structured_json/{S}.json` already present → `extraction_status = ready`
2. Not present → `extraction_status = needs_extraction`

After noise removal, only BSEE PDFs have pre-existing JSONs. All CSB PDFs start as `needs_extraction`.

---

## Manifest Schema

`data/corpus_v1/manifests/corpus_v1_manifest.csv`

| Column | Description |
|--------|-------------|
| `incident_id` | URL-decoded PDF stem |
| `source_agency` | `BSEE` or `CSB` (inferred from `raw_pdfs/` path origin) |
| `pdf_filename` | Bare filename with extension |
| `pdf_path` | Relative path from repo root |
| `json_path` | Relative path, or `PENDING` if needs extraction |
| `extraction_status` | `ready` or `needs_extraction` |

---

## Implementation Tasks

1. **Build manifest** — generate `corpus_v1_manifest.csv` by cross-referencing `raw_pdfs/` vs `structured_json/`.
2. **Clean structured_json** — move no-match JSONs to `structured_json_noise/`.
3. **Extract CSB** — for each `needs_extraction` PDF, call Claude (Anthropic provider) with the v2.3 extraction prompt, write output to `structured_json/`. Update manifest to `ready`.

---

## Source Agency Inference

- PDF path contains `/bsee/` → `BSEE`
- PDF path contains `/csb/` → `CSB`
- (For corpus_v1, all PDFs in `raw_pdfs/` are known to be either BSEE or CSB; provenance was set at copy time.)

Since `raw_pdfs/` is flat, agency is tracked in the manifest only. At copy time, BSEE files came from `data/raw/bsee/pdfs/` and CSB files from `data/raw/csb/pdf/`.
