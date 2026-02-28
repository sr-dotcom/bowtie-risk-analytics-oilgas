"""Abstract base for LLM providers."""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for LLM extraction providers."""

    @abstractmethod
    def extract(self, prompt: str) -> str:
        """Send prompt to LLM and return raw response string.

        Args:
            prompt: Fully assembled prompt with schema and incident text.

        Returns:
            Raw JSON string from the LLM.
        """
        ...
