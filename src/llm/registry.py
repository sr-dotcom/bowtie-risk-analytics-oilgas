"""Provider registry: resolve provider name to LLMProvider instance."""
import os
from typing import Optional

from src.llm.base import LLMProvider

SUPPORTED_PROVIDERS = ("stub", "openai", "anthropic", "gemini")

_ENV_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def get_provider(name: str, model: Optional[str] = None) -> LLMProvider:
    """Return an LLMProvider instance for *name*.

    Args:
        name: One of ``stub``, ``openai``, ``anthropic``, ``gemini``.
        model: Model identifier passed to non-stub providers (ignored by stub).

    Returns:
        An instantiated :class:`LLMProvider`.

    Raises:
        ValueError: If *name* is not a supported provider.
        RuntimeError: If a required API-key env-var is missing for non-stub
            providers.
    """
    if name not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown provider: {name!r}. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    if name == "stub":
        from src.llm.stub import StubProvider
        return StubProvider()

    # Non-stub: fail-fast on missing API key
    env_var = _ENV_KEY_MAP[name]
    api_key = os.environ.get(env_var)
    if not api_key:
        raise RuntimeError(
            f"Provider {name!r} requires env var {env_var} but it is not set."
        )

    # Placeholder – real SDK wrappers will be added later
    raise NotImplementedError(
        f"Provider {name!r} is registered but not yet implemented. "
        f"Set {env_var} and implement src/llm/{name}.py."
    )
