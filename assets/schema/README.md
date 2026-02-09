# Incident Schema v2.3

This directory contains the Schema v2.3 incident definition for the Bowtie Risk Analytics pipeline.

## Files

- `incident_v2_2_template.json` -- Full JSON template with safe defaults for all fields.

## Top-Level Sections

| Section       | Description                                                       |
|---------------|-------------------------------------------------------------------|
| `incident_id` | Unique identifier string for the incident.                       |
| `source`      | Document metadata: type, URL, title, dates, timezone.            |
| `context`     | Operational context: region, operator, phase, materials.         |
| `event`       | Event details: top event, type, costs, actions, summary, etc.    |
| `bowtie`      | Bowtie diagram elements: hazards, threats, consequences, controls.|
| `pifs`        | Performance Influencing Factors grouped by people, work, org.    |
| `notes`       | Schema metadata and extraction rules.                            |

## Enum Values

### `side` (control placement on the bowtie)
- `"prevention"` -- Left side; prevents top event from occurring.
- `"mitigation"` -- Right side; reduces consequence severity.

### `barrier_status`
- `"active"` -- Barrier was functioning as intended.
- `"degraded"` -- Barrier was partially effective.
- `"failed"` -- Barrier did not perform its function.
- `"bypassed"` -- Barrier was deliberately circumvented.
- `"not_installed"` -- Barrier was not present at the facility.
- `"unknown"` -- Status could not be determined from the report.

### `barrier_type`
- `"engineering"` -- Hardware or design-based control.
- `"administrative"` -- Procedure, policy, or management control.
- `"ppe"` -- Personal protective equipment.
- `"unknown"` -- Type could not be determined.

### `line_of_defense`
- `"1st"` -- Primary barrier closest to the hazard.
- `"2nd"` -- Secondary backup barrier.
- `"3rd"` -- Tertiary or emergency barrier.
- `"recovery"` -- Post-event recovery measure.
- `"unknown"` -- Line of defense could not be determined.

### `confidence`
- `"high"` -- Strong textual evidence in the source document.
- `"medium"` -- Reasonable inference from available text.
- `"low"` -- Weak or no direct evidence; default for template.

## Field Conventions

### `*_mentioned` (boolean)
Indicates whether the factor was explicitly referenced in the source document. Must be evidence-based: set to `true` only when the source text contains a clear reference to the factor.

### `*_applicable` (boolean)
Indicates whether a detection/alarm/intervention mechanism is relevant to the control. For example, `detection_applicable` is `true` when the barrier type could reasonably include a detection component.

### `*_value` (Optional[str])
Free-text field capturing the extracted detail for a PIF or human factor. Set to `null` when the factor is not mentioned or the value cannot be determined.

### Relationship Between `*_mentioned` and `*_value`
- If `*_mentioned` is `false`, `*_value` should be `null`.
- If `*_mentioned` is `true`, `*_value` should contain the extracted evidence text.
