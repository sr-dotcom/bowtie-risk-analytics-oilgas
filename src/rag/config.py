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
