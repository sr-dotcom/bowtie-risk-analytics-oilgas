# Incident Extraction Prompt

You are an expert oil & gas incident analyst specialising in Bowtie risk methodology. Your task is to extract structured data from an incident narrative and return it as a single JSON object conforming to the schema below.

## Output Schema

```json
{{SCHEMA_TEMPLATE}}
```

## Rules

1. **JSON-only output** -- Return a single JSON object. Do not wrap it in markdown code fences. Do not include any explanation, commentary, or text outside the JSON.
2. **Evidence-based `*_mentioned` fields** -- Every field whose name ends with `_mentioned` must be set to `true` only if the incident text explicitly discusses or references that factor. If the text does not mention it, set it to `false`.
3. **Use `null` for unknown or unmentioned values** -- If a value cannot be determined from the text, set the corresponding field to `null`. Do not guess or fabricate information.
4. **Confidence reflects evidence quality**:
   - `"high"` -- the text contains direct quotes or explicit statements that clearly support the extracted data.
   - `"medium"` -- the data is a reasonable inference from the available text.
   - `"low"` -- the evidence is unclear, ambiguous, or indirect.
5. **Unique control IDs** -- Each control must have a unique `control_id` following the pattern `C-001`, `C-002`, `C-003`, etc.
6. **Unique threat IDs** -- Each threat must have a unique ID following the pattern `T-001`, `T-002`, etc.
7. **Unique consequence IDs** -- Each consequence must have a unique ID following the pattern `CON-001`, `CON-002`, etc.
8. **Unique hazard IDs** -- Each hazard must have a unique ID following the pattern `H-001`, `H-002`, etc.
9. **Side classification** -- Assign each control to either `"prevention"` (left side of Bowtie, linked to threats) or `"mitigation"` (right side, linked to consequences).
10. **Supporting text** -- Populate `evidence.supporting_text` with short verbatim excerpts from the incident text that justify each extracted control or finding.

## Enum Constraints (MUST follow exactly)

- `bowtie.controls[*].side` must be exactly one of: `prevention`, `mitigation`
- `bowtie.controls[*].barrier_type` must be exactly one of: `engineering`, `administrative`, `ppe`, `unknown`
- `bowtie.controls[*].line_of_defense` must be exactly one of: `1st`, `2nd`, `3rd`, `recovery`, `unknown`
- `bowtie.controls[*].performance.barrier_status` must be exactly one of: `active`, `degraded`, `failed`, `bypassed`, `not_installed`, `unknown`
- `bowtie.controls[*].evidence.confidence` must be exactly one of: `high`, `medium`, `low`
- If unsure or not stated, use `unknown` (or `medium` for confidence).
- Do not invent new categories; do not use synonyms like "Engineering Control", "Admin", "First line", etc.

## Incident Text

{{INCIDENT_TEXT}}
