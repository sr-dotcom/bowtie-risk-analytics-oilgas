"""Provider registry: resolve provider name to LLMProvider instance."""
import os
from typing import Any, Optional

from src.llm.base import LLMProvider

SUPPORTED_PROVIDERS = ("stub", "anthropic")

_ENV_KEY_MAP = {
        "anthropic": "ANTHROPIC_API_KEY",
    }


def get_provider(name: str, model: Optional[str] = None, **kwargs: Any) -> LLMProvider:
    """Return an LLMProvider instance for *name*.

    Args:
        name: One of ``stub``, ``openai``, ``anthropic``, ``gemini``.
        model: Model identifier passed to non-stub providers (ignored by stub).
        **kwargs: Extra keyword arguments forwarded to the provider constructor
            (e.g. ``max_output_tokens``, ``temperature``, ``timeout``, ``retries``).

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
    if name == "anthropic":
        from src.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model, **kwargs)
    raise ValueError(f"Unknown provider: {name!r}")
