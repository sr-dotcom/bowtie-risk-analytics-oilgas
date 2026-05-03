"""Project-wide pytest hooks.

Currently:
- Emits a warning at collection time if cascade ML artifacts are missing,
  since several test modules use ``pytest.mark.skipif`` to silently skip
  when artifacts are absent. The warning prevents the "all tests pass
  while N silently skipped" failure mode for receivers running pytest
  on a fresh clone.

Per AUDIT_TRIAGE F017.
"""
from __future__ import annotations

import warnings
from pathlib import Path

_CASCADE_ARTIFACT = Path("data/models/artifacts/xgb_cascade_y_fail_pipeline.joblib")


def pytest_configure(config):
    """Warn if the cascade pipeline artifact is missing.

    When this artifact is absent, every test gated by
    ``pytest.mark.skipif(_ARTIFACTS_MISSING, ...)`` will silently skip.
    Surfacing the absence at session start prevents misleading green
    test summaries on fresh clones.
    """
    if not _CASCADE_ARTIFACT.exists():
        warnings.warn(
            f"Cascade artifact missing: {_CASCADE_ARTIFACT}. "
            "Tests gated on artifact presence will be skipped silently. "
            "Run `python -m src.modeling.cascading.train` to generate it. "
            "See AUDIT_TRIAGE F017 for context.",
            UserWarning,
            stacklevel=1,
        )
