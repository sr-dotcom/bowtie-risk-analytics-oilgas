<!--
chapter: 8
title: Lessons Learned
audience: Process safety domain expert evaluator + faculty supervisor
last-verified: 2026-04-27
wordcount: ~970
-->

# Chapter 8 — Lessons Learned

The seven preceding chapters documented what was built. This chapter argues what was learned from building it. The argument draws from specific events in the project record — decisions that were reversed, errors that prior documentation had carried, choices that held up and why. Five lessons follow; each is grounded in evidence from the chapters that precede it.

## External evaluation perspective beat internal building-instinct

Three design events in this project share a structural feature: each was resolved by external evaluation, none by internal iteration.

Chapter 3's cascade pivot came from domain expert review comments (Fidel Comments #12, #56, #63) — pathway-awareness, CCPS taxonomy alignment, threat-based conditioning, all flagged externally. Months of single-barrier modeling had not surfaced them. Chapter 5's cross-domain filter came from pre-demo verification: AB Specialty Silicones, a chemical batch tank rupture in Waukegan, Illinois, was appearing as evidence for offshore PSV barrier predictions. Internal review had not caught it. Chapter 2 and 4's taxonomy distinctions — PIF framing and the LoD dual-system — sharpened under the same review pressure.

The lesson is not that domain experts matter. Formal review and pre-demo testing are structurally different evaluation modes than building: they access failure states the building team cannot manufacture for itself. The project's correct response was to treat those perspectives as architectural inputs, not commentary on completed work.

## Pre-declared protocols help most when results are far from the boundary

The y_hf_fail protocol held. The question is under what conditions.

D016 pre-declared three production branches before measurement. D019 tightened them to strict total-ordering. The measured AUC — 0.556, with one fold at 0.401 — activated Branch C without ambiguity: the result cleared no threshold, the consequence followed automatically, and no post-hoc judgment was required. That is real discipline: declaring the logic before the result, then applying it.

What the y_hf_fail case did not test is the harder version. A result at 0.59 or 0.61 — close enough to the 0.60 floor that measurement uncertainty matters — requires the same discipline but at substantially higher cost. Pre-declared thresholds are easiest to honor when the result makes it easy. The lesson from Chapter 3 is humbler than "the protocol worked": it is that the protocol was tested under favorable conditions, and the favorable conditions did most of the work.

## Constraint-driven engineering choices are local truths

Four choices in this project are local truths. They should not be presented as anything else.

Chapter 7's single-container deployment was correct for a team without dedicated DevOps — the alternative architectures assume infrastructure maintenance the project couldn't sustain. Chapter 6's custom SVG choice was correct given BowTieXP visual fidelity requirements; a generic graph library would have produced brittle layout workarounds rather than meeting the constraint directly. The no-visual-regression decision (K001, K002) was correct given absent QA infrastructure — manual browser verification was the available mechanism, and the chapter records that as engineering reality, not a gap. Chapter 4's M002 ablation framing as advisory rather than authoritative was correct given the sample-size ceiling that prevented an M003-equivalent ablation from running.

Each choice was justified by a specific constraint. The constraint, not the choice, is what future maintainers need to recover. When the constraint changes — team composition, infrastructure, sample size — the choice should be reconsidered, not assumed to still hold.

## Documentation accuracy is a function of grounding methodology

The journey chapters found three documentation errors in prior internal documentation: the production architecture was described as three containers; it runs as one. The active risk thresholds differed from the values carried in the model artifact. The training row count was off by one — 530 actual where the milestone description had expected 529.

None of these were caught by prior documentation effort. All three were caught by the same methodology: read the actual code and artifacts first, propose structure based on what was found, draft against verified findings. Prior internal documentation had been written against memory or against earlier intermediate documents — methodologies that compound errors silently over time.

The lesson is not that the prior documentation was careless. It is that writing carefully from memory still produces drift. The journey chapters did not try harder; they grounded differently. That is the distinction that determined accuracy.

## Domain expertise was applied through review, not embodied

The CCPS taxonomy is enforced by code. Its meaning is in the domain.

That distinction applies across the project. The cascade architecture (Chapter 3), the cross-domain filter (Chapter 5), the threshold calibration (Chapter 3) — each carries the outcome of domain expert review, not the expertise itself. The decision register holds the rationale: why the CCPS 11-category taxonomy was adopted, why thresholds were set where they were. The rationale lives there because it cannot live in the code.

The maintenance implication is direct. A future engineer without process safety context can change the taxonomy mapping, recalibrate the thresholds, or expand the retrieval corpus in ways the system cannot flag as domain-incorrect. Code will run; the domain constraint will be violated silently.

This is not a critique of the project. It is naming an unstated maintenance dependency that the journey chapters surface and the system itself cannot.

## What this chapter buys and what it doesn't

Five lessons are now on record. External evaluation modes — formal review, pre-demo verification — surfaced architecture changes that months of internal iteration had not. Pre-declared branch logic held when the result was unambiguous; the harder test, a result near the threshold, remains untested. Constraint-driven choices are local truths, scoped to the operating conditions of this practicum; none transfers without verifying that the underlying constraint holds. Documentation accuracy is a function of grounding methodology, not care or effort: source-first drafting found errors that memory-based documentation had carried silently. Domain expertise shaped the system through review; the expertise itself was not encoded, leaving maintenance decisions that the decision register describes but the code cannot enforce.

**What this chapter buys**
- External evaluation modes catch failure states the building team cannot manufacture
- Pre-declared protocols held under unambiguous results; borderline cases untested
- Constraint-driven engineering choices are local truths, not universal recommendations
- Documentation accuracy is a function of grounding methodology
- Domain expertise is applied through review; the system carries outcomes, not expertise

**What this chapter doesn't buy**
- Generalizations beyond this project — the lessons are scoped to the practicum record
- Prescriptions for future projects — observational, not protocol-defining
- Whether the lessons replicate at different scales or in different domains — unverified
