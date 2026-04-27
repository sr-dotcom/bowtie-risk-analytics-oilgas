# Chapter 8 — Lessons Learned

**Status: deferred to post-Apr-27**
**Audience: process safety domain expert evaluator + faculty supervisor**
**Last verified: 2026-04-27**

---

This chapter is intentionally deferred.

The seven preceding chapters describe what was built: the problem framing (Chapter 1), the corpus design (Chapter 2), the cascade model (Chapter 3), the explanation signals (Chapter 4), the RAG pipeline (Chapter 5), the frontend (Chapter 6), and the deployment (Chapter 7). Together they form the technical arc of the practicum.

A lessons-learned chapter is a different kind of writing. It argues about what was learned across the project — which engineering choices held up, which framings turned out to be wrong, which constraints mattered more than expected, and what would be done differently if started today. That argument is hard to make honestly while the work is still finishing. The chapter requires distance from the artifact to be useful.

Chapter 8 will be written after the Apr 27 final presentation, with appropriate time to reflect on what the practicum actually taught — not what it would be convenient to say it taught.

When written, the chapter is expected to address:

- The cascade pivot (D008): what the structural-not-statistical hypothesis bought, and what the 156-incident corpus could not test about it.
- The y_hf_fail decision (D016): pre-declared branch logic as a discipline pattern, and what it cost to drop a target the project initially scoped as essential.
- The RAG miss rate (40% Top-10): what cross-domain filtering and the 156-incident corpus jointly bound, and the limits of retrieval against narrow domain corpora.
- The PIF exclusion (D011) and the M002 ablation evidence: structural hypotheses confirmed by ablation, and the boundary of carrying M002 evidence into M003 architecture.
- The custom BowtieSVG choice: visual-fidelity-driven engineering work, and the cost of owning a bespoke layout engine without visual regression coverage.
- The single-container production deployment: simplicity bought at the cost of HA, and what the SPOF would mean operationally beyond a demo context.
- The journey-documentation discipline itself: what documenting in-flight engineering against verified source actually costs, and what it produces that other documentation modes do not.

---

Source grounds (when written): the seven preceding chapters; `docs/decisions/DECISIONS.md` (D006-D019); `docs/knowledge/KNOWLEDGE.md` (K-entries surfaced during chapter authoring); `docs/evaluation/EVALUATION.md` (M002 ablation evidence and per-fold CV results).
