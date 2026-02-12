# Association Mining Data Prep

This folder provides a small, reproducible two-step workflow for preparing incident data for association mining:

1. **Aggregate** normalized incident JSON files into one JSON list.
2. **Flatten** each incident's bowtie controls into a row-based table for modeling.

## Default input

By default, aggregation reads normalized Schema v2.3 incidents from:

- `data/structured/incidents/schema_v2_3`

Generate that folder first if needed:

```bash
python -m src.pipeline convert-schema --incident-dir data/structured/incidents/anthropic --out-dir data/structured/incidents/schema_v2_3
```

## Commands

### 1) Aggregate incidents

```bash
python scripts/association_mining/jsonaggregation.py
```

Optional arguments:

- `--input-dir` (default: `data/structured/incidents/schema_v2_3`)
- `--output-json` (default: `out/association_mining/incidents_aggregated.json`)

### 2) Flatten to CSV

```bash
python scripts/association_mining/jsonflattening.py
```

Optional arguments:

- `--input-json` (default: `out/association_mining/incidents_aggregated.json`)
- `--output-csv` (default: `out/association_mining/incidents_flat.csv`)
- `--output-xlsx` (optional; omitted by default)

Example with optional XLSX output:

```bash
python scripts/association_mining/jsonflattening.py --output-xlsx out/association_mining/incidents_flat.xlsx
```

## Output location

Generated files are written under:

- `out/association_mining/`

This keeps generated artifacts out of version control and reproducible on demand.
