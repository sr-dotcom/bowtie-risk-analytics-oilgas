# Bowtie Risk Analytics - Executive Summary v2

## System Overview

Bowtie Risk Analytics is a risk intelligence platform designed for oil and gas safety professionals. The system applies the Bowtie risk methodology to analyze barrier effectiveness across Loss of Containment scenarios, drawing on a foundation of 739 real incident reports and 4,776 barrier controls extracted from investigations by the Chemical Safety Board (CSB), Bureau of Safety and Environmental Enforcement (BSEE), Pipeline and Hazardous Materials Safety Administration (PHMSA), and the Transportation Safety Board of Canada (TSB).

The platform performs a **historical reliability assessment** for each barrier in a user's Bowtie diagram. Rather than providing abstract scores, it answers a concrete operational question: *Which barriers in this Bowtie are most likely to be weak or fail, and why?* Each assessment is grounded in evidence from similar real-world barrier failures, giving risk professionals actionable intelligence they can use to prioritize barrier strengthening efforts.

Risk professionals input their Bowtie barriers and receive a multi-layered analysis: a High, Medium, or Low risk level based on historical failure patterns, identification of the degradation factors most likely to compromise barrier integrity, evidence narratives drawn from similar incidents in the corpus, and 2-3 actionable recommendations for barrier strengthening.

## Methodology

The historical reliability assessment methodology is built on three complementary analytical layers:

**XGBoost Classification Models.** Two gradient-boosted models trained on historical incident data assess barrier reliability. Model 1 evaluates overall barrier failure likelihood based on barrier characteristics and operational context. Model 2 assesses human factor sensitivity, identifying which degradation factors are most likely to contribute to barrier compromise. Both models were validated using GroupKFold cross-validation (grouped by incident to prevent data leakage), achieving F1 scores of 0.885 and 0.696 respectively.

**SHAP-Based Degradation Factor Analysis.** TreeExplainer generates per-barrier SHAP (SHapley Additive exPlanations) values that quantify each degradation factor's contribution to the assessed risk level. This transforms opaque model outputs into interpretable factor-by-factor breakdowns, showing exactly which conditions increase or decrease concern for a given barrier.

**RAG-Powered Evidence Retrieval.** A 4-stage hybrid retrieval pipeline (metadata filtering, dual FAISS semantic search, intersection, Reciprocal Rank Fusion) identifies the most relevant historical barrier failures from a corpus of 526 incidents and 3,253 barrier controls. Retrieved evidence is synthesized into narratives by an LLM (Anthropic Claude) that grounds its analysis in real incident data, not speculation.

## Risk Level Classification

Each barrier's historical reliability assessment produces a risk level classification:

| Risk Level | Definition | Threshold |
|------------|-----------|-----------|
| **High** | Top 20% of historical failure patterns | At or above the 80th percentile (p80) of training distribution |
| **Medium** | Middle 40% of historical failure patterns | Between the 60th percentile (p60) and 80th percentile |
| **Low** | Bottom 40% of historical failure patterns | Below the 60th percentile |

These thresholds are derived from the statistical distribution of the training data, not from subjective judgment. The p80 and p60 percentile boundaries are computed during model training and stored as calibrated reference points. This ensures that risk levels reflect the actual distribution of historical barrier performance across the corpus.

## Barrier Analysis Framework

The system applies a 5-layer analysis framework to each barrier:

1. **Barrier Type Classification.** Each barrier is classified into one of four process safety categories (Engineering, Administrative, Human, Operational) based on YAML mapping tables aligned with industry standards. This classification contextualizes the barrier within established safety frameworks.

2. **Line of Defense Assignment.** Barriers are assigned to their appropriate line of defense category, positioning them within the defense-in-depth hierarchy. The system uses an 11-category classification that maps to standard process safety line-of-defense frameworks.

3. **Degradation Factor Identification.** Twelve degradation factors (derived from Performance Influencing Factors in the incident data) are evaluated for each barrier. SHAP analysis quantifies each factor's contribution, producing a ranked list of the conditions most likely to compromise barrier integrity.

4. **Evidence Retrieval from Similar Incidents.** The RAG pipeline retrieves barrier failures from the historical corpus that share similar characteristics. A confidence gate ensures that only sufficiently relevant evidence is presented, with a minimum cosine similarity threshold to prevent hallucinated or weakly-grounded narratives.

5. **Actionable Recommendations.** Based on the degradation factor analysis and retrieved evidence, the system generates 2-3 specific, actionable recommendations for strengthening the barrier. Each recommendation is grounded in lessons learned from similar historical barrier failures.

## Degradation Factors

The system tracks 12 degradation factors that influence barrier reliability. These are Performance Influencing Factors from the incident data, reframed as degradation factors per process safety standards to emphasize their role in barrier compromise:

| Degradation Factor | Category | Description |
|---|---|---|
| Operator Competence | People | Skill and knowledge gaps affecting barrier operation |
| Operator Fatigue | People | Fatigue-related degradation of barrier monitoring and response |
| Communication Breakdown | People | Failures in information transfer affecting barrier coordination |
| Situational Awareness Loss | People | Loss of real-time understanding of barrier state and conditions |
| Procedural Failure | Work | Inadequate, outdated, or non-followed procedures for barrier use |
| Excessive Workload | Work | Task overload degrading attention to barrier integrity |
| Time Pressure | Work | Schedule pressure leading to shortcuts in barrier maintenance |
| Tools and Equipment Deficiency | Work | Inadequate or degraded tools needed for barrier function |
| Safety Culture Weakness | Organisation | Organizational norms that tolerate barrier degradation |
| Management of Change Failure | Organisation | Uncontrolled changes that compromise barrier effectiveness |
| Inadequate Supervision | Organisation | Insufficient oversight of barrier-related activities |
| Insufficient Training | Organisation | Gaps in training for barrier operation and maintenance |

Each degradation factor is presented with its SHAP contribution value, indicating whether it increases or decreases concern for the barrier under assessment. A plain-English summary ranks the top contributing factors (e.g., "Primary degradation factors: Operator Fatigue (strong), Procedural Failure (moderate)").

## Evidence and Recommendations

The evidence pipeline retrieves relevant historical barrier failures and generates grounded narratives using a 4-stage hybrid retrieval approach:

- **Metadata Filtering:** Narrows the corpus to barriers matching the query's barrier family and side (prevention/mitigation)
- **Dual FAISS Semantic Search:** Parallel searches on barrier-level and incident-level embeddings using all-mpnet-base-v2 sentence transformers
- **Intersection and RRF Ranking:** Combines results via Reciprocal Rank Fusion to balance precision and recall across both index types
- **Confidence Gate:** Only evidence above the cosine similarity threshold is passed to the LLM for narrative generation, preventing weakly-grounded output

The corpus comprises 526 incidents and 3,253 barrier controls across 25 barrier families. Retrieved evidence is synthesized into a narrative by Anthropic Claude, which is instructed to ground all analysis in the specific retrieved incidents and use historical reliability assessment terminology throughout.

Each analysis includes 2-3 actionable recommendations generated by the LLM based on the degradation factor analysis and evidence from similar incidents. Recommendations are specific to the barrier under assessment and cite the types of failures observed in similar historical cases, ensuring they are operationally relevant rather than generic.

## Key Terminology

The following terminology changes align the system's user-facing language with process safety standards:

| Previous Term | Current Term | Rationale |
|---|---|---|
| Prediction | Historical Reliability Assessment | Reflects that assessments are based on historical incident data patterns, not forward-looking certainty |
| Failure Probability | Risk Level (High / Medium / Low) | Categorical levels are more actionable for risk professionals than continuous probabilities |
| Performance Influencing Factors (PIFs) | Degradation Factors | Emphasizes the mechanism by which these factors compromise barrier integrity |
| Risk Score (1-10) | High / Medium / Low Risk Level | Eliminates false precision; categorical levels match decision-making practice |
| Barrier Status | Barrier Condition Characterization | Describes the assessed condition of a barrier based on historical patterns |

## Technical Architecture

The system is built as a two-tier web application:

- **Backend:** Python FastAPI with three endpoints (/predict, /explain, /health). Models loaded at startup via lifespan pattern. Asynchronous thread offloading for LLM calls to maintain event loop responsiveness.
- **Frontend:** Next.js with React Flow for interactive Bowtie diagram visualization. Supports both a graph Diagram View and a two-column Pathway View (Prevention/Mitigation barrier card grid). SHAP waterfall charts rendered via Recharts.
- **ML Models:** XGBoost classifiers with TreeExplainer for SHAP values. OrdinalEncoder for categorical features with unknown-value handling.
- **RAG Pipeline:** FAISS IndexFlatIP for cosine similarity search, Reciprocal Rank Fusion for result merging, optional cross-encoder reranker (ms-marco-MiniLM-L-6-v2).
- **LLM Integration:** Anthropic Claude for evidence narrative generation with confidence gating and structured recommendation output.
- **Configuration:** YAML mapping files for all process safety terminology translations (barrier types, lines of defense, degradation factors, barrier conditions).

## Data Sources

| Source | Agency | Coverage |
|---|---|---|
| CSB | U.S. Chemical Safety and Hazard Investigation Board | Major chemical incident investigation reports |
| BSEE | Bureau of Safety and Environmental Enforcement | Offshore oil and gas safety alerts and investigation reports |
| PHMSA | Pipeline and Hazardous Materials Safety Administration | Pipeline incident investigation data |
| TSB | Transportation Safety Board of Canada | Transportation safety investigation reports |

The combined corpus contains 739 structured incidents with 4,776 barrier controls, all normalized to Schema V2.3 with Pydantic validation.

## Review History

This document reflects the incorporation of domain expert review feedback from **Fidel Ilizastigui Perez**, who provided 14 comments on the Bowtie Risk Analytics system. All comments were addressed in Phase 8 (Domain Expert Alignment), which implemented:

- Barrier type and line of defense mapping tables aligned with process safety standards (Comments #6, #9, #12, #34)
- PIF-to-degradation-factor terminology reframing (Comment #12)
- Reframing of all user-facing text to use "historical reliability assessment" terminology (Comments #2, #30)
- High/Medium/Low risk level classification replacing numeric scores (Comment #63)
- Barrier condition characterization terminology (Comment #59)
- Recommendations in RAG evidence output (Comment #64)
- Prevention and mitigation pathway-grouped barrier views (Comments #55, #56)
- Executive summary update with process safety terminology (Comment #61)

---

*Version: 2.0 | Phase: 08-domain-expert-alignment | Date: 2026-04-01*
