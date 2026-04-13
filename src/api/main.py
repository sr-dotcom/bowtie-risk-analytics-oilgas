from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

"""FastAPI application for Bowtie Risk Analytics.

Endpoints:
  POST /predict  — barrier failure probability + SHAP reason codes (API-01, D-01, D-02)
  POST /explain  — RAG evidence narrative for a barrier (API-02, D-03, D-04)
  GET  /health   — service status with loaded model artifact info (API-03, D-08)

All ML resources are loaded exactly once at startup via the async lifespan
context manager and stored on app.state (D-05, D-06, API-04).
AnthropicProvider calls in /explain are wrapped in asyncio.to_thread()
to avoid blocking the event loop (D-07, API-05).
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.mapping_loader import MappingConfig
from src.api.schemas import (
    AprioriRule,
    AprioriRulesResponse,
    CitationResponse,
    DegradationFactor,
    ExplainRequest,
    ExplainResponse,
    FeatureMetadata,
    HealthResponse,
    ModelInfo,
    PredictRequest,
    PredictResponse,
    RagInfo,
    ShapValue,
)
from src.modeling.predict import BarrierPredictor
from src.rag.config import CONFIDENCE_THRESHOLD
from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider
from src.rag.explainer import BarrierExplainer
from src.rag.rag_agent import RAGAgent
from src.llm.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)

# Default artifact paths — configurable via environment or constructor
ARTIFACTS_DIR = Path("data/models/artifacts")
RAG_DIR = Path("data/evaluation/rag_workspace")


# ---------------------------------------------------------------------------
# Lifespan — load all resources once at startup (D-05, D-06, API-04)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Load ML models and RAG resources exactly once at startup (D-05, D-06).

    Stores on app.state for endpoint access:
      app.state.predictor       — BarrierPredictor
      app.state.explainer       — BarrierExplainer
      app.state.start_time      — float (monotonic)
      app.state.rag_corpus_size — int
    """
    start_time = time.monotonic()

    # Load BarrierPredictor (Phase 3 artifact)
    predictor = BarrierPredictor(artifacts_dir=ARTIFACTS_DIR)
    logger.info("BarrierPredictor loaded from %s", ARTIFACTS_DIR)

    # Load RAG agent + BarrierExplainer (Phase 4 artifact)
    embedding_provider = SentenceTransformerProvider()
    rag_agent = RAGAgent.from_directory(RAG_DIR, embedding_provider)

    # AnthropicProvider with haiku for cost-efficient narratives (D-07)
    llm_provider = AnthropicProvider(
        model="claude-haiku-4-5-20251001",
        max_output_tokens=1500,
    )
    explainer = BarrierExplainer(rag_agent=rag_agent, llm_provider=llm_provider)
    logger.info("BarrierExplainer loaded from %s", RAG_DIR)

    # Load process safety terminology mappings (Phase 8)
    mapping_config = MappingConfig.load()
    logger.info("MappingConfig loaded from configs/mappings/")

    # Load Apriori co-failure rules (S03)
    apriori_rules_path = Path("data/evaluation/apriori_rules.json")
    if apriori_rules_path.exists():
        with open(apriori_rules_path) as f:
            apriori_data = json.load(f)
        apriori_rules_list = apriori_data["rules"]
        logger.info(
            "Loaded %d Apriori rules from %s",
            len(apriori_rules_list),
            apriori_rules_path,
        )
    else:
        apriori_rules_list = []
        logger.warning(
            "Apriori rules not found at %s — endpoint will return empty list",
            apriori_rules_path,
        )

    # Store on app.state for endpoint access (D-05)
    app.state.predictor = predictor
    app.state.explainer = explainer
    app.state.start_time = start_time
    app.state.rag_corpus_size = len(rag_agent._barrier_meta)
    app.state.mapping_config = mapping_config
    app.state.apriori_rules = apriori_rules_list

    yield  # App runs here

    # Cleanup — read-only resources, nothing to release
    logger.info("Shutting down — resources released")


# ---------------------------------------------------------------------------
# App factory — routes registered inside to bind to the correct app instance
# ---------------------------------------------------------------------------

def create_app(lifespan_override: Any = None) -> FastAPI:
    """Create FastAPI application with lifespan and CORS.

    Routes are registered inside this function so they attach to the returned
    app instance. This allows tests to pass a no-op lifespan via
    ``lifespan_override`` and inject mocked resources without loading real
    model artifacts.

    Args:
        lifespan_override: Optional lifespan context manager to use instead of
            the default. Used in tests to inject mocked resources.

    Returns:
        Configured FastAPI application with all routes registered.
    """
    app = FastAPI(
        title="Bowtie Risk Analytics API",
        version="0.1.0",
        description="Barrier failure prediction and evidence narrative API",
        lifespan=lifespan_override or lifespan,
    )

    # CORS — permissive for development; tighten origins in Phase 7 (D-05 discretion)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # POST /predict — barrier failure probability + SHAP reason codes (API-01)
    # -----------------------------------------------------------------------

    @app.post("/predict", response_model=PredictResponse)
    async def predict(request: PredictRequest, req: Request) -> PredictResponse:
        """Predict barrier failure probability with SHAP reason codes.

        Accepts raw 18-field feature dict (D-01).
        Returns probabilities + SHAP values for both models (D-02).
        Resources are loaded once in lifespan — no per-request loading (D-06).

        Args:
            request: PredictRequest with 18 barrier feature fields.
            req: Raw FastAPI request (used to access app.state).

        Returns:
            PredictResponse with model probabilities, SHAP lists, and feature metadata.

        Raises:
            HTTPException: 422 if prediction fails due to invalid features.
        """
        predictor: BarrierPredictor = req.app.state.predictor
        features = request.model_dump()

        # top_event_category and source_agency are incident-level features that
        # the frontend doesn't supply per-barrier. PredictRequest provides safe
        # defaults ("loss_of_containment", "UNKNOWN") so this dict is already
        # complete — no manual injection needed here.

        try:
            result = predictor.predict(features)
        except Exception as exc:
            logger.exception("Prediction failed: %s", exc)
            raise HTTPException(status_code=422, detail=str(exc))

        # Convert SHAP dicts to ShapValue lists with category metadata
        feature_meta = predictor.feature_names  # list[dict] with name + category
        category_map = {f["name"]: f["category"] for f in feature_meta}

        model1_shap = [
            ShapValue(feature=name, value=val, category=category_map.get(name, "barrier"))
            for name, val in result.model1_shap_values.items()
        ]
        model2_shap = [
            ShapValue(feature=name, value=val, category=category_map.get(name, "barrier"))
            for name, val in result.model2_shap_values.items()
        ]
        feature_metadata = [
            FeatureMetadata(name=f["name"], category=f["category"])
            for f in feature_meta
        ]

        # Phase 8: Process safety terminology mapping (D-03, D-07, Fidel-#6,#9,#12,#34,#59,#63)
        mapping: MappingConfig = req.app.state.mapping_config

        # Degradation factors: PIF SHAP values mapped to process safety names
        degradation_factors = [
            DegradationFactor(
                factor=mapping.get_degradation_factor(sv.feature),
                source_feature=sv.feature,
                contribution=sv.value,
            )
            for sv in model1_shap
            if sv.category == "incident_context"
        ]
        degradation_factors.sort(key=lambda x: abs(x.contribution), reverse=True)

        # Risk level: H/M/L from probability (D-07)
        risk_level = mapping.compute_risk_level(result.model1_probability)

        # Display names for barrier_type and line_of_defense (D-01, Fidel-#6, Fidel-#9)
        barrier_type_display = mapping.get_barrier_type_display(
            features.get("barrier_type", "")
        )
        lod_display = mapping.get_lod_display(
            features.get("line_of_defense", "")
        )

        # Barrier condition display (Fidel-#59) — empty at prediction time;
        # populated when barrier_status is known (e.g., from a broader context)
        barrier_condition_display = ""

        return PredictResponse(
            model1_probability=result.model1_probability,
            model2_probability=result.model2_probability,
            model1_shap=model1_shap,
            model2_shap=model2_shap,
            model1_base_value=result.model1_base_value,
            model2_base_value=result.model2_base_value,
            feature_metadata=feature_metadata,
            degradation_factors=degradation_factors,
            risk_level=risk_level,
            barrier_type_display=barrier_type_display,
            lod_display=lod_display,
            barrier_condition_display=barrier_condition_display,
        )

    # -----------------------------------------------------------------------
    # GET /health — service status with model artifact info (API-03)
    # -----------------------------------------------------------------------

    @app.get("/health", response_model=HealthResponse)
    async def health(req: Request) -> HealthResponse:
        """Service health with loaded model artifact info (D-08).

        Args:
            req: Raw FastAPI request (used to access app.state).

        Returns:
            HealthResponse with status, model info, RAG info, and uptime.
        """
        uptime = time.monotonic() - req.app.state.start_time

        return HealthResponse(
            status="ok",
            models={
                "model1": ModelInfo(
                    type="XGBoost",
                    path=str(ARTIFACTS_DIR / "xgb_model1.json"),
                    loaded=True,
                ),
                "model2": ModelInfo(
                    type="XGBoost",
                    path=str(ARTIFACTS_DIR / "xgb_model2.json"),
                    loaded=True,
                ),
            },
            rag=RagInfo(
                corpus_size=req.app.state.rag_corpus_size,
                threshold=CONFIDENCE_THRESHOLD,
            ),
            uptime_seconds=round(uptime, 2),
        )

    # -----------------------------------------------------------------------
    # GET /apriori-rules — pre-computed Apriori co-failure rules (S03)
    # -----------------------------------------------------------------------

    @app.get("/apriori-rules", response_model=AprioriRulesResponse)
    async def apriori_rules(req: Request) -> AprioriRulesResponse:
        """Return pre-computed Apriori barrier co-failure association rules (S03).

        Rules are loaded once at startup from data/models/artifacts/apriori_rules.json.
        Returns an empty list if the artifact was not present at startup.

        Args:
            req: Raw FastAPI request (used to access app.state).

        Returns:
            AprioriRulesResponse with a list of AprioriRule objects.
        """
        return AprioriRulesResponse(
            rules=[AprioriRule(**r) for r in req.app.state.apriori_rules]
        )

    # -----------------------------------------------------------------------
    # POST /explain — RAG evidence narrative for a barrier (API-02)
    # -----------------------------------------------------------------------

    @app.post("/explain", response_model=ExplainResponse)
    async def explain(request: ExplainRequest, req: Request) -> ExplainResponse:
        """Generate RAG evidence narrative for a barrier (API-02).

        Wraps BarrierExplainer.explain() in asyncio.to_thread() because
        AnthropicProvider.extract() is blocking (uses requests.post) — it
        MUST NOT block the FastAPI event loop (D-07, API-05).

        Args:
            request: ExplainRequest with barrier context and optional SHAP factors.
            req: Raw FastAPI request (used to access app.state).

        Returns:
            ExplainResponse with narrative, citations, retrieval_confidence, model_used.

        Raises:
            HTTPException: 500 if BarrierExplainer.explain() raises an unexpected error.
        """
        explainer: BarrierExplainer = req.app.state.explainer

        # Build barrier query matching corpus text structure for better cosine similarity.
        # Corpus format: "Barrier: {name}\nRole: {role}\nLOD Basis: {basis}"
        # We use barrier_type + barrier_family as a proxy for barrier name (not in request).
        barrier_query = (
            f"Barrier: {request.barrier_type} - {request.barrier_family}\n"
            f"Role: {request.barrier_role}"
        )
        logger.info(
            "explain: barrier_family=%s query_len=%d",
            request.barrier_family,
            len(barrier_query),
        )

        # Build incident query from event_description (text describing the incident)
        incident_query = request.event_description

        # Convert ShapValue list to dict[str, float] for BarrierExplainer (D-03)
        shap_dict: dict[str, float] | None = None
        if request.shap_factors:
            shap_dict = {sv.feature: sv.value for sv in request.shap_factors}

        # Phase 8: Use risk_level from request if provided (Bug #3 fix — client
        # sends prediction context), otherwise fall back to empty string.
        risk_level_str = request.risk_level or ""

        logger.info(
            "Explain request: family=%s, side=%s, role=%.60s",
            request.barrier_family,
            request.side,
            request.barrier_role,
        )

        try:
            # CRITICAL: asyncio.to_thread() prevents blocking the event loop (D-07, API-05)
            # BarrierExplainer.explain() calls AnthropicProvider.extract() which uses
            # synchronous requests.post — running it in a thread keeps the loop responsive
            result = await asyncio.to_thread(
                explainer.explain,
                barrier_query=barrier_query,
                incident_query=incident_query,
                shap_factors=shap_dict,
                risk_level=risk_level_str,
                barrier_family=request.barrier_family,
            )
        except Exception as exc:
            logger.exception("Explain failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

        # Convert Citation objects to CitationResponse Pydantic models
        citations = [
            CitationResponse(
                incident_id=c.incident_id,
                control_id=c.control_id,
                barrier_name=c.barrier_name,
                barrier_family=c.barrier_family,
                supporting_text=c.supporting_text,
                relevance_score=c.relevance_score,
                incident_summary=c.incident_summary,
            )
            for c in result.citations
        ]

        return ExplainResponse(
            narrative=result.narrative,
            citations=citations,
            retrieval_confidence=result.retrieval_confidence,
            model_used=result.model_used,
            recommendations=result.recommendations,  # Phase 8 (D-12)
        )

    return app


# Module-level app instance for uvicorn and production use
app = create_app()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
