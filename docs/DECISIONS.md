# Architecture Decisions

## Overview
This document records key architecture and design decisions for the Bowtie Risk Analytics project.

---

## Decisions

### ADR-002: Use Streamlit for MVP Demo Dashboard
**Date:** Project initialization  
**Status:** Accepted

**Context:**
Need a fast, reproducible way to present pipeline outputs (control coverage, gap analysis, risk score, explanations) in a simple interactive demo UI, without over-investing in front-end engineering.

**Decision:**
Use Streamlit for the MVP dashboard (demo surface), not as a production web application framework.

**Alternatives considered:**
- Plotly Dash (more structure, similar Python-first UI)
- FastAPI + React (high flexibility, higher build cost)
- Jupyter/Voila (quick sharing, weaker app feel)

**Consequences:**
- Rapid prototyping and easy local runs for grading/demo
- Limited UI customization compared to full web frameworks
- Deployment: primary goal is a hosted Streamlit demo if permitted; local run remains the fallback

---

### ADR-001: Use Pydantic v2 for Data Models and Schema Validation
**Date:** Project initialization  
**Status:** Accepted

**Context:**
Need robust validation/serialization for structured JSON used throughout the pipeline:
- Bowtie schema (hazards, threats, barriers/controls, consequences, escalation factors)
- Incident extraction schema (structured fields extracted from narratives for analytics/model features)

**Decision:**
Use Pydantic v2 as the canonical schema layer for all JSON models and validation in the pipeline.

**Alternatives considered:**
- Python dataclasses + JSON Schema (more manual wiring)
- Pandera (better for tabular validation; less ideal for nested JSON)
- No formal validation (higher risk of silent data issues)

**Consequences:**
- Strong runtime validation and consistent serialization/deserialization
- Earlier failure on malformed inputs (improves debugging and reproducibility)
- Requires version pinning (Pydantic v2 behavior changes can be breaking)

---

*Add new decisions above this line*
