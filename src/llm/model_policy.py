from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Set, Optional

import yaml


@dataclass(frozen=True)
class ModelPolicy:
    provider: str
    default_model: str
    fallback_models: List[str]
    retries_per_model: int
    promote_on: Set[str]

    @staticmethod
    def load(path: str | Path = "configs/model_policy.yaml") -> "ModelPolicy":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Model policy file not found: {p}")

        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

        provider = str(raw.get("provider", "anthropic")).strip()
        default_model = str(raw.get("default_model", "claude-sonnet-4-6")).strip()

        fallback_models = raw.get("fallback_models") or []
        fallback_models = [str(x).strip() for x in fallback_models if str(x).strip()]

        # Ensure the default is always in the ladder (in a sensible spot)
        if default_model not in fallback_models:
            fallback_models = [fallback_models[0]] + [default_model] + fallback_models[1:] if fallback_models else [default_model]

        retries_per_model = int(raw.get("retries_per_model", 2))

        promote_on = raw.get("promote_on") or []
        promote_on = {str(x).strip() for x in promote_on if str(x).strip()}

        # Safe defaults
        if not promote_on:
            promote_on = {"timeout", "rate_limit", "invalid_json", "schema_validation_failed", "empty_output"}

        return ModelPolicy(
            provider=provider,
            default_model=default_model,
            fallback_models=fallback_models,
            retries_per_model=retries_per_model,
            promote_on=promote_on,
        )
