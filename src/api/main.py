from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

"""FastAPI application for Bowtie Risk Analytics.

Endpoints:
  POST /predict-cascading — cascading barrier failure probability + SHAP (S03)
  POST /rank-targets      — lightweight ranking without SHAP (S03)
  POST /explain-cascading — RAG evidence + degradation context (S03)
  GET  /health            — service status with loaded model artifact info (API-03, D-08)
  GET  /apriori-rules     — pre-computed Apriori co-failure rules (S03)
  GET  /predict           — 410 Gone (migrated to /predict-cascading)
  GET  /explain           — 410 Gone (migrated to /explain-cascading)

All ML resources are loaded exactly once at startup via the async lifespan
context manager and stored on app.state.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import hmac

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from src.api.mapping_loader import MappingConfig
from src.api.schemas import (
    AprioriRule,
    AprioriRulesResponse,
    CascadingRequest,
    CascadingShapValue,
    CascadingBarrierPrediction,
    DegradationContext,
    EvidenceSnippet,
    ExplainCascadingRequest,
    ExplainCascadingResponse,
    GoneResponse,
    HealthResponse,
    ModelInfo,
    PredictCascadingResponse,
    RagInfo,
    RankedBarrier,
    RankTargetsResponse,
)
from src.modeling.cascading.predict import load_cascading_predictor
from src.rag.embeddings.sentence_transformers_provider import SentenceTransformerProvider
from src.rag.pair_context_builder import build_pair_context
from src.rag.rag_agent import RAGAgent

logger = logging.getLogger(__name__)

# Default artifact paths — configurable via environment or constructor
ARTIFACTS_DIR = Path("data/models/artifacts")
RAG_V2_DIR = Path("data/rag/v2")


# ---------------------------------------------------------------------------
# Lifespan — load all resources once at startup (D-05, D-06, API-04)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Load ML models and RAG resources exactly once at startup.

    Stores on app.state for endpoint access:
      app.state.cascading_predictor — CascadingPredictor (None on load failure)
      app.state.rag_v2_agent        — RAGAgent for v2 corpus (None on load failure)
      app.state.start_time          — float (monotonic)
      app.state.rag_corpus_size     — int
      app.state.apriori_rules       — list[dict]
    """
    start_time = time.monotonic()

    # Load shared embedding provider (reused across all RAG agents)
    embedding_provider = SentenceTransformerProvider()

    # Load CascadingPredictor — graceful degradation if artifact missing
    cascading_predictor = None
    try:
        cascading_predictor = load_cascading_predictor(ARTIFACTS_DIR)
        logger.info("CascadingPredictor loaded from %s", ARTIFACTS_DIR)
    except Exception as exc:
        logger.warning("CascadingPredictor not loaded — predict-cascading will degrade: %s", exc)

    # Load RAGAgent v2 for cascading explain endpoint
    rag_v2_agent = None
    rag_v2_corpus_size = 0
    if RAG_V2_DIR.exists():
        try:
            rag_v2_agent = RAGAgent.from_directory(RAG_V2_DIR, embedding_provider)
            rag_v2_corpus_size = len(rag_v2_agent._barrier_meta)
            logger.info("RAGAgent v2 loaded from %s (%d barriers)", RAG_V2_DIR, rag_v2_corpus_size)
        except Exception as exc:
            logger.warning("RAGAgent v2 not loaded — explain-cascading will degrade: %s", exc)
    else:
        logger.warning("RAG v2 directory not found at %s", RAG_V2_DIR)

    # Load Apriori co-failure rules
    apriori_rules_path = Path("data/evaluation/apriori_rules.json")
    if apriori_rules_path.exists():
        with open(apriori_rules_path) as f:
            apriori_data = json.load(f)
        apriori_rules_list = apriori_data["rules"]
        logger.info("Loaded %d Apriori rules from %s", len(apriori_rules_list), apriori_rules_path)
    else:
        apriori_rules_list = []
        logger.warning("Apriori rules not found at %s — endpoint will return empty list", apriori_rules_path)

    # Store on app.state for endpoint access
    app.state.cascading_predictor = cascading_predictor
    app.state.rag_v2_agent = rag_v2_agent
    app.state.start_time = start_time
    app.state.rag_corpus_size = rag_v2_corpus_size
    app.state.apriori_rules = apriori_rules_list

    yield  # App runs here

    logger.info("Shutting down — resources released")


# ---------------------------------------------------------------------------
# API key authentication — disabled when BOWTIE_API_KEY is unset
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> None:
    required_key = os.getenv("BOWTIE_API_KEY")
    if not required_key:
        return
    if not api_key or not hmac.compare_digest(api_key, required_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


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
    enable_docs = os.getenv("BOWTIE_ENABLE_DOCS", "").lower() == "true"
    app = FastAPI(
        title="Bowtie Risk Analytics API",
        version="0.1.0",
        description="Barrier failure prediction and evidence narrative API",
        lifespan=lifespan_override or lifespan,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    # CORS — restricted origins from env; defaults to localhost for dev
    allowed_origins = [
        o.strip()
        for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    # -----------------------------------------------------------------------
    # GET /predict — 410 Gone (migrated to /predict-cascading)
    # -----------------------------------------------------------------------

    @app.get("/predict")
    async def predict_gone() -> JSONResponse:
        """Legacy /predict endpoint — permanently removed (S03).

        Returns HTTP 410 Gone with migration hint.
        """
        return JSONResponse(
            status_code=410,
            content=GoneResponse(migrate_to="/predict-cascading").model_dump(),
        )

    # -----------------------------------------------------------------------
    # GET /explain — 410 Gone (migrated to /explain-cascading)
    # -----------------------------------------------------------------------

    @app.get("/explain")
    async def explain_gone() -> JSONResponse:
        """Legacy /explain endpoint — permanently removed (S03).

        Returns HTTP 410 Gone with migration hint.
        """
        return JSONResponse(
            status_code=410,
            content=GoneResponse(migrate_to="/explain-cascading").model_dump(),
        )

    # -----------------------------------------------------------------------
    # GET /health — service status (API-03)
    # -----------------------------------------------------------------------

    @app.get("/health", response_model=HealthResponse)
    async def health(req: Request) -> HealthResponse:
        """Service health with loaded model artifact info."""
        uptime = time.monotonic() - req.app.state.start_time
        cascading_loaded = req.app.state.cascading_predictor is not None
        rag_v2_loaded = req.app.state.rag_v2_agent is not None

        return HealthResponse(
            status="ok",
            models={
                "cascading": ModelInfo(name="xgb_cascade_y_fail", loaded=cascading_loaded),
                "rag_v2": ModelInfo(name="rag_v2", loaded=rag_v2_loaded),
            },
            rag=RagInfo(corpus_size=req.app.state.rag_corpus_size),
            uptime_seconds=round(uptime, 2),
        )

    # -----------------------------------------------------------------------
    # GET /apriori-rules — pre-computed Apriori co-failure rules
    # -----------------------------------------------------------------------

    @app.get("/apriori-rules", response_model=AprioriRulesResponse, dependencies=[Depends(verify_api_key)])
    async def apriori_rules(req: Request) -> AprioriRulesResponse:
        """Return pre-computed Apriori barrier co-failure association rules."""
        return AprioriRulesResponse(
            rules=[AprioriRule(**r) for r in req.app.state.apriori_rules]
        )

    # -----------------------------------------------------------------------
    # POST /predict-cascading — cascading barrier failure predictions (S03)
    # -----------------------------------------------------------------------

    @app.post("/predict-cascading", response_model=PredictCascadingResponse, dependencies=[Depends(verify_api_key)])
    async def predict_cascading(request: CascadingRequest, req: Request) -> PredictCascadingResponse:
        """Predict cascading barrier failure for all non-conditioning barriers.

        On predictor load failure, returns empty predictions with explanation_unavailable=True.
        """
        predictor = req.app.state.cascading_predictor
        if predictor is None:
            return PredictCascadingResponse(predictions=[], explanation_unavailable=True)

        # Validate conditioning_barrier_id exists in scenario
        barrier_ids = [b.get("control_id") for b in request.scenario.get("barriers", [])]
        if request.conditioning_barrier_id not in barrier_ids:
            raise HTTPException(
                status_code=400,
                detail=f"conditioning_barrier_id '{request.conditioning_barrier_id}' not found in scenario barriers",
            )

        try:
            result = predictor.predict(request.scenario, request.conditioning_barrier_id)
        except Exception as exc:
            logger.exception("Cascading prediction failed: %s", exc)
            return PredictCascadingResponse(predictions=[], explanation_unavailable=True)

        predictions = [
            CascadingBarrierPrediction(
                target_barrier_id=p.target_barrier_id,
                y_fail_probability=p.y_fail_probability,
                risk_band=p.risk_band,
                shap_values=[
                    CascadingShapValue(feature=sv.feature, value=sv.value)
                    for sv in p.shap_values
                ],
            )
            for p in result.predictions
        ]
        return PredictCascadingResponse(predictions=predictions)

    # -----------------------------------------------------------------------
    # POST /rank-targets — lightweight ranking without SHAP (S03)
    # -----------------------------------------------------------------------

    @app.post("/rank-targets", response_model=RankTargetsResponse, dependencies=[Depends(verify_api_key)])
    async def rank_targets(request: CascadingRequest, req: Request) -> RankTargetsResponse:
        """Rank non-conditioning barriers by failure probability (no SHAP)."""
        predictor = req.app.state.cascading_predictor
        if predictor is None:
            return RankTargetsResponse(ranked_barriers=[])

        barrier_ids = [b.get("control_id") for b in request.scenario.get("barriers", [])]
        if request.conditioning_barrier_id not in barrier_ids:
            raise HTTPException(
                status_code=400,
                detail=f"conditioning_barrier_id '{request.conditioning_barrier_id}' not found in scenario barriers",
            )

        try:
            result = predictor.rank(request.scenario, request.conditioning_barrier_id)
        except Exception as exc:
            logger.exception("Ranking failed: %s", exc)
            return RankTargetsResponse(ranked_barriers=[])

        return RankTargetsResponse(
            ranked_barriers=[
                RankedBarrier(
                    target_barrier_id=rb.target_barrier_id,
                    composite_risk_score=rb.composite_risk_score,
                )
                for rb in result.ranked_barriers
            ]
        )

    # -----------------------------------------------------------------------
    # POST /explain-cascading — RAG evidence + degradation context (S03)
    # -----------------------------------------------------------------------

    @app.post("/explain-cascading", response_model=ExplainCascadingResponse, dependencies=[Depends(verify_api_key)])
    async def explain_cascading(request: ExplainCascadingRequest, req: Request) -> ExplainCascadingResponse:
        """Build RAG evidence narrative for a (conditioning, target) barrier pair.

        RAG-only — does NOT call an LLM. SHAP is on /predict-cascading.
        """
        rag_v2: RAGAgent | None = req.app.state.rag_v2_agent
        if rag_v2 is None:
            return ExplainCascadingResponse(
                narrative_text="",
                evidence_snippets=[],
                degradation_context=DegradationContext(pif_mentions=[], recommendations=[], barrier_condition=""),
                narrative_unavailable=True,
            )

        scenario = request.bowtie_context
        barriers = scenario.get("barriers", [])
        barrier_map = {b.get("control_id"): b for b in barriers}

        conditioning = barrier_map.get(request.conditioning_barrier_id)
        target = barrier_map.get(request.target_barrier_id)

        if conditioning is None:
            raise HTTPException(status_code=400, detail=f"conditioning_barrier_id '{request.conditioning_barrier_id}' not found")
        if target is None:
            raise HTTPException(status_code=400, detail=f"target_barrier_id '{request.target_barrier_id}' not found")

        # Build incident context from scenario fields
        ctx = scenario.get("context", {})
        incident_context: dict[str, Any] = {
            "top_event": scenario.get("top_event", ""),
            "operating_phase": ctx.get("operating_phase", ""),
            "materials": ctx.get("materials", []),
        }

        try:
            pair_result = await asyncio.to_thread(
                build_pair_context,
                conditioning,
                target,
                rag_v2,
                incident_context,
            )
        except Exception as exc:
            logger.exception("explain-cascading RAG retrieval failed: %s", exc)
            return ExplainCascadingResponse(
                narrative_text="",
                evidence_snippets=[],
                degradation_context=DegradationContext(pif_mentions=[], recommendations=[], barrier_condition=""),
                narrative_unavailable=True,
            )

        narrative_unavailable = bool(pair_result.empty_retrievals)

        # Build evidence snippets from target results
        evidence_snippets: list[EvidenceSnippet] = []
        incident_meta_store = getattr(rag_v2, "_incident_meta", {})
        for rr in pair_result.target_results:
            inc_meta = incident_meta_store.get(rr.incident_id, {})
            evidence_snippets.append(EvidenceSnippet(
                incident_id=rr.incident_id,
                source_agency=inc_meta.get("source_agency", ""),
                text=f"Barrier family: {rr.barrier_family} (RRF score: {rr.rrf_score:.4f})",
                score=rr.rrf_score,
            ))

        # PIF mentions — truthy keys from scenario pif_context
        pif_context = scenario.get("pif_context", {})
        pif_mentions: list[str] = []
        for group, items in pif_context.items():
            if isinstance(items, dict):
                for key, val in items.items():
                    if val:
                        pif_mentions.append(f"{group}.{key}")

        # Recommendations — collect from retrieved conditioning incident metadata
        recommendations: list[str] = []
        seen_recs: set[str] = set()
        for rr in (pair_result.conditioning_results + pair_result.target_results):
            inc_meta = incident_meta_store.get(rr.incident_id, {})
            raw_recs = inc_meta.get("recommendations", "[]")
            try:
                parsed = json.loads(raw_recs) if isinstance(raw_recs, str) else []
                for rec in parsed:
                    rec_str = str(rec).strip()
                    if rec_str and rec_str not in seen_recs:
                        seen_recs.add(rec_str)
                        recommendations.append(rec_str)
                        if len(recommendations) >= 5:
                            break
            except (json.JSONDecodeError, TypeError):
                pass
            if len(recommendations) >= 5:
                break

        # barrier_condition from the conditioning barrier
        barrier_condition = conditioning.get("barrier_condition", "")

        return ExplainCascadingResponse(
            narrative_text=pair_result.context_text,
            evidence_snippets=evidence_snippets,
            degradation_context=DegradationContext(
                pif_mentions=pif_mentions,
                recommendations=recommendations,
                barrier_condition=barrier_condition,
            ),
            narrative_unavailable=narrative_unavailable,
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
