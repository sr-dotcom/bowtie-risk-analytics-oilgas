"""RAG retrieval pipeline constants."""

# Default embedding model
DEFAULT_EMBEDDING_MODEL = "all-mpnet-base-v2"
EMBEDDING_DIMENSION = 768

# Retrieval pipeline defaults
TOP_K_BARRIERS = 50
TOP_K_INCIDENTS = 20
TOP_K_FINAL = 10

# RRF parameter
RRF_K = 60

# Context builder
MAX_CONTEXT_CHARS = 8000

# Reranker (Phase-2)
RERANKER_ENABLED = True
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_MAX_LENGTH = 512
RERANKER_BATCH_SIZE = 32
TOP_K_RERANK = 30
FINAL_TOP_K = 10

# Confidence gate (Phase 4 — RAG-to-LLM wiring)
# Calibrated: demo queries score 0.20-0.52; P90 corpus pairs = 0.65
CONFIDENCE_THRESHOLD = 0.25
