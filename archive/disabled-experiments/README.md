# archive/disabled-experiments/

Code and tests from experiments that were intentionally disabled per architectural decision but retained for reference and future re-evaluation.

## Contents

### `hf_recovery.py` + `test_s02b_hf_recovery.py`

Implements the y_hf_fail Branch C path (Performance Influencing Factor recovery model) and its companion test suite.

**Status:** disabled per **D016**.

The y_hf_fail model achieved AUC 0.556 ± 0.118 on cross-validation — below the 0.60 floor specified in the pre-registered branch-activation logic (D016, refined by D019). Branch C (the catch-all "do not surface in production" path) was activated. The model and its tests remain runnable as historical reference but are not part of the M003 production pipeline.

**Re-activation criteria:** corpus expansion to materially more samples (current ceiling: 56/156 incidents carry HF positives), per primer Deliberate Deferrals.

**Restorability:** to re-activate the experiment in active source:

```bash
git mv archive/disabled-experiments/hf_recovery.py src/modeling/cascading/hf_recovery.py
git mv archive/disabled-experiments/test_s02b_hf_recovery.py tests/test_s02b_hf_recovery.py
```

Verify imports remain valid (originally none beyond self-references) and update CLAUDE.md module list + docs/evidence/architecture/factual-audit-part2.md table reference.

**Source decisions:**

- D016 — pre-registered branch-activation logic
- D019 — Branch B definition refinement (catch-all Branch C semantics)
- AUDIT_TRIAGE F015 — move-to-archive over delete (council 3/2 lean)
- TRIAGE.md — Phase 2 audit triage
