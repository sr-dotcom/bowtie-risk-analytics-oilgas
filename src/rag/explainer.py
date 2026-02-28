"""Evidence narrative generator: RAG retrieval + confidence gate + LLM synthesis."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.llm.base import LLMProvider
from src.rag.config import CONFIDENCE_THRESHOLD
from src.rag.rag_agent import RAGAgent, ExplanationResult
from src.rag.retriever import RetrievalResult

# Prompt template path (per D-04: lives in src/prompts/)
_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "explain_barrier.md"

# Non-PIF feature display names for LLM prompt context (hardcoded — no YAML exists for these)
_NON_PIF_DISPLAY_NAMES: dict[str, str] = {
    "source_agency": "Data Source",
    "barrier_family": "Barrier Family",
    "side": "Pathway Position",
    "barrier_type": "Barrier Classification",
    "supporting_text_count": "Evidence Volume",
    "line_of_defense": "Line of Defense",
    "controls_per_incident": "Controls Density",
    "top_event_category": "Event Category",
}


def _load_feature_display_names() -> dict[str, str]:
    """Build feature name -> display name mapping for LLM prompt.

    Merges hardcoded non-PIF names with PIF names from pif_to_degradation.yaml.
    Falls back gracefully if the YAML file is absent.
    """
    names = dict(_NON_PIF_DISPLAY_NAMES)
    # configs/ is at project root: explainer.py -> rag/ -> src/ -> project_root/
    pif_yaml = (
        Path(__file__).resolve().parent.parent.parent
        / "configs" / "mappings" / "pif_to_degradation.yaml"
    )
    if pif_yaml.exists():
        import yaml  # imported here to avoid top-level dep if yaml unavailable
        data = yaml.safe_load(pif_yaml.read_text(encoding="utf-8"))
        names.update(data.get("pif_to_degradation", {}))
    return names


_FEATURE_DISPLAY_NAMES: dict[str, str] = _load_feature_display_names()


@dataclass
class Citation:
    """A single evidence citation pinned to a specific barrier (D-08)."""

    incident_id: str
    control_id: str
    barrier_name: str
    barrier_family: str
    supporting_text: str    # first excerpt from barrier corpus (D-10)
    relevance_score: float  # barrier_sim_score (cosine similarity)
    incident_summary: str = ""  # incident-level summary for "Similar Incidents" display


class BarrierExplainer:
    """Orchestrates RAG retrieval + LLM narrative generation.

    Uses AnthropicProvider (D-01) with claude-haiku-4-5 (D-02).
    Confidence gate at CONFIDENCE_THRESHOLD (D-05, D-06, D-07).
    """

    def __init__(self, rag_agent: RAGAgent, llm_provider: LLMProvider) -> None:
        self._rag = rag_agent
        self._llm = llm_provider

    def explain(
        self,
        barrier_query: str,
        incident_query: str,
        shap_factors: dict[str, float] | None = None,
        risk_level: str = "",  # Phase 8: H/M/L label for LLM context (D-09)
        **kwargs: Any,
    ) -> ExplanationResult:
        """Generate evidence narrative for a barrier.

        Args:
            barrier_query: Description of the barrier being analyzed.
            incident_query: Description of the incident context.
            shap_factors: Optional dict of feature_name -> SHAP value from
                PredictionResult. Top factors are included in the LLM prompt
                as a "Model Analysis" section (D-03).
            **kwargs: Passed to RAGAgent.explain() (barrier_family, top_k, etc.)

        Returns:
            ExplanationResult with narrative, citations, retrieval_confidence.
            If confidence gate fires (D-05), narrative is "No matching incidents
            found." and model_used is "none".
        """
        # Step 1: Retrieve similar barriers via RAGAgent
        retrieval = self._rag.explain(barrier_query, incident_query, **kwargs)

        # Step 2: Confidence gate (RAG-02, D-05, D-06, D-07)
        # Use barrier_sim_score NOT rrf_score (Pitfall 3 from RESEARCH.md)
        best_score = max(
            (r.barrier_sim_score for r in retrieval.results), default=0.0
        )

        if best_score < CONFIDENCE_THRESHOLD:
            return ExplanationResult(
                context_text=retrieval.context_text,
                results=retrieval.results,
                metadata=retrieval.metadata,
                narrative="No matching incidents found.",
                citations=[],
                retrieval_confidence=best_score,
                model_used="none",
            )

        # Step 3: Build citations from retrieval results (RAG-04, D-08, D-10)
        citations = self._build_citations(retrieval.results)

        # Step 4: Build prompt with optional SHAP section (D-03, D-04)
        prompt = self._build_prompt(
            barrier_query, retrieval.context_text, shap_factors, risk_level
        )

        # Step 5: Call LLM (D-01, D-02) -- method is extract(), NOT generate()
        raw_response = self._llm.extract(prompt)

        # Step 6: Parse recommendations from LLM response (Phase 8, D-12)
        narrative_text, recommendations = self._parse_recommendations(raw_response)

        return ExplanationResult(
            context_text=retrieval.context_text,
            results=retrieval.results,
            metadata=retrieval.metadata,
            narrative=narrative_text,
            citations=citations,
            retrieval_confidence=best_score,
            model_used=getattr(self._llm, "model", "unknown"),
            recommendations=recommendations,
        )

    @staticmethod
    def _parse_recommendations(llm_response: str) -> tuple[str, str]:
        """Split LLM response into narrative and recommendations sections.

        The prompt instructs the LLM to output '## Recommendations' as a delimiter.

        Args:
            llm_response: Full LLM response text.

        Returns:
            Tuple of (narrative, recommendations). If delimiter not found,
            returns (full_response, "").
        """
        delimiter = "## Recommendations"
        if delimiter in llm_response:
            parts = llm_response.split(delimiter, 1)
            return parts[0].strip(), parts[1].strip()
        return llm_response.strip(), ""

    def _build_citations(
        self, results: list[RetrievalResult]
    ) -> list[Citation]:
        """Build Citation objects from retrieval results and barrier metadata."""
        citations: list[Citation] = []
        for r in results:
            b_meta = self._rag._find_barrier_meta(r)

            # Extract barrier_name from barrier_role_match_text (same as rag_agent.py)
            barrier_text = b_meta.get("barrier_role_match_text", "")
            lines = barrier_text.split("\n")
            barrier_name = lines[0].replace("Barrier: ", "") if lines else ""

            # Extract supporting_text from JSON-encoded list (D-10)
            raw_st = b_meta.get("supporting_text", "[]")
            try:
                st_list: list[str] = json.loads(raw_st) if raw_st else []
            except (json.JSONDecodeError, TypeError):
                st_list = []
            # Take first excerpt, truncate to 500 chars
            supporting_text = st_list[0][:500] if st_list else ""

            # Extract incident_summary from barrier metadata (populated by corpus_builder.py)
            incident_summary = b_meta.get("incident_summary", "")

            citations.append(Citation(
                incident_id=r.incident_id,
                control_id=r.control_id,
                barrier_name=barrier_name,
                barrier_family=r.barrier_family,
                supporting_text=supporting_text,
                relevance_score=r.barrier_sim_score,
                incident_summary=incident_summary,
            ))
        return citations

    def _build_prompt(
        self,
        barrier_query: str,
        context_text: str,
        shap_factors: dict[str, float] | None,
        risk_level: str = "",
    ) -> str:
        """Build LLM prompt from template with variable substitution."""
        template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

        # Build SHAP section (D-03) -- empty string if no SHAP provided
        shap_section = ""
        if shap_factors:
            # Sort by absolute SHAP value descending, take top 5
            sorted_factors = sorted(
                shap_factors.items(), key=lambda kv: abs(kv[1]), reverse=True
            )[:5]
            lines = [
                "## Model Analysis",
                "",
                "The historical reliability assessment identified these top degradation factors for this barrier:",
            ]
            for name, val in sorted_factors:
                direction = "increases failure risk" if val > 0 else "decreases failure risk"
                display_name = _FEATURE_DISPLAY_NAMES.get(name, name)
                lines.append(f"- {display_name}: {val:+.3f} ({direction})")
            shap_section = "\n".join(lines)

        prompt = template.replace("{{BARRIER_QUERY}}", barrier_query)
        prompt = prompt.replace("{{RISK_LEVEL_LABEL}}", risk_level if risk_level else "Not assessed")
        prompt = prompt.replace("{{RETRIEVED_EVIDENCE}}", context_text)
        prompt = prompt.replace("{{SHAP_ANALYSIS}}", shap_section)
        return prompt
