# UI-CONTEXT.md — Bowtie Risk Analytics Visual Standards (v2.4)

This document is the visual design source of truth for the Bowtie Risk Analytics dashboard. Every UI brief (T1–T4 and beyond) must read this file first. CCCLI references this when implementing components.

**Audience:** modern industrial. Loosened ISA-101 — process safety domain experts (Fidel Ilizastigui Perez), academic reviewers (Dr. Ilieva Ageenko + UNC Charlotte faculty), and portfolio/screenshot viewers (LinkedIn, thesis defense). Visually credible to all three; insider-only to none.

**Mode:** dark-only for M003. Light mode is explicitly out of scope (see Section 14).

---

## 1. Design philosophy

The product is a process-safety analytics dashboard. It tells the user which barriers in their bowtie are most likely to fail, why, and what historical evidence backs that prediction. The UI must:

- Look like operations software, not a marketing site
- Project authority — the user trusts the predictions
- Stay out of the way — the data is the hero
- Photograph well on a projector, in a screenshot, in a print PDF

What it must NOT look like:

- Bento grids, glassmorphism, claymorphism, neumorphism, or any current SaaS trend
- Gradient buttons, neon accents, large rounded cards floating in space
- Marketing landing pages, hero CTAs, "get started free" energy
- A consumer mobile app

If a design choice would feel at home on a Stripe-style landing page, it's wrong for this project.

---

## 2. ISA-101 principles applied (loosened)

ISA-101 is the international standard for human-machine interface design in process industries. We follow its principles, not its strict prescriptions:

- Color is for meaning, not decoration. Saturated red, amber, green only signal risk state. Not used for branding, decoration, or visual interest elsewhere.
- Depressurized neutrals. Backgrounds, surfaces, borders use desaturated charcoal/slate. The user's eye should rest on neutrals and snap to color only when something matters.
- Hierarchy through contrast and weight, not color. Headlines and important values use lighter text or higher contrast — not blue or accent colors.
- No decorative iconography. Icons exist when functional (settings gear, close X, expand chevron). No mascot, no illustration, no Unsplash hero photos.
- Density is acceptable. Process engineers expect data-dense screens. Don't over-pad in the name of "modern minimalism" — that reads as wasted space.

---

## 3. Palette — locked

### Backgrounds (cool charcoal, three depths)

| Token | Hex | Use |
|---|---|---|
| `bg.base` | `#0F1419` | Page background |
| `bg.surface` | `#151B24` | Cards, panels, metric blocks, sidebar |
| `bg.elevated` | `#1C2430` | Hover states, dropdowns, drill-down panel, form inputs |
| `bg.accent` | `#1A2332` | Narrative hero strip, callouts |

### Borders (desaturated)

| Token | Hex | Use |
|---|---|---|
| `border.subtle` | `#1F2937` | Default card borders, table row dividers |
| `border.default` | `#2A3442` | Emphasized / hover, form input borders |
| `border.strong` | `#3A4556` | Focus / selected, active tab |

### Text (near-white, never pure)

| Token | Hex | Use |
|---|---|---|
| `text.primary` | `#E8E8E8` | Headings, values, primary labels |
| `text.secondary` | `#9CA3AF` | Body, supporting labels |
| `text.tertiary` | `#6B7280` | Metadata, captions, axis labels, placeholder text |
| `text.inverse` | `#0F1419` | Text on filled buttons / colored pill backgrounds |

### Risk semantic (muted ISA-101)

| Token | Hex | Use |
|---|---|---|
| `risk.high` | `#C0392B` | High-risk pill background, barrier risk band |
| `risk.highText` | `#E74C3C` | Risk text on dark surface, SHAP positive (risk-up) |
| `risk.medium` | `#996515` | Medium-risk pill background, olive amber |
| `risk.mediumText` | `#D68910` | Medium text on dark surface |
| `risk.low` | `#1F6F43` | Low-risk pill background, muted forest |
| `risk.lowText` | `#27AE60` | Low text on dark surface |
| `risk.unknown` | `#4A5568` | Slate gray for "?" / no-data |

These eight risk colors are the ONLY non-neutral colors that appear at scale. Everything else is grayscale + accent.

### Accent (single steel-blue family)

| Token | Hex | Use |
|---|---|---|
| `accent.primary` | `#2C5F7F` | Links, primary buttons, focus rings, SHAP negative (risk-down) |
| `accent.hover` | `#3A7399` | Hover state |
| `accent.active` | `#1F4A66` | Pressed state |
| `accent.subtle` | `#1A3344` | Faint blue tint for info pills, "similar incidents" inline links |

There is exactly ONE accent family. No purple, no teal, no pink anywhere. Steel blue does the work of "interactive."

### Effects

| Token | Value | Use |
|---|---|---|
| `shadow.focus` | `0 0 0 2px #2C5F7F66` | Focus ring on inputs, buttons, interactive elements |
| `shadow.drill` | `0 8px 24px rgba(0, 0, 0, 0.4)` | Optional shadow under drill-down drawer if it overlays |

### Tailwind allowlist exception (chips only)

The following Tailwind utility classes are PRESERVED in existing PIF-mention chips and similar semantic badges. Do NOT refactor these to tokens:

- `bg-amber-500/15`, `text-amber-400`, `border-amber-500/30` (warning chips)
- `bg-blue-500/15`, `text-blue-400`, `border-blue-500/30` (info chips)
- `bg-red-500/15`, `text-red-400`, `border-red-500/30` (danger chips)

Rationale: these are semantic Tailwind utilities (warning/info/danger) using restrained alpha overlays. They render at chip scale only and visually align with the muted risk palette. Replacing them with custom tokens adds maintenance cost without visual benefit. Treat them as a stable pattern.

**Scope of the allowlist:** chip-style elements only (small labels with alpha backgrounds). Standalone Tailwind color classes on raw text (`text-red-400`, `text-amber-400`, `text-green-400` on spans, paragraphs, headings) are NOT allowlisted — they go through tokens (`risk.highText`, `risk.mediumText`, `risk.lowText` via inline style or CSS var).

### Forbidden colors

These never appear in the dashboard chrome (the bowtie SVG interior is exempt — see Section 7):

- Pure black `#000000` or pure white `#FFFFFF`
- Browser-default red/blue/green (`#FF0000`, `#0000FF`, `#00FF00`)
- Any neon, fluorescent, or saturated tertiary color
- Tailwind's `purple-*`, `pink-*`, `teal-*`, `indigo-*`, `cyan-*`, `fuchsia-*`, `rose-*`, `violet-*` — full ramps forbidden
- Non-allowlisted uses of `red-*`, `green-*`, `amber-*`, `blue-*` — the chip utilities in the allowlist above are the ONLY approved uses
- Gradients of any kind (one exception: the BowTieXP connector tab gradient already in BowtieSVG)

---

## 4. Typography

Font stack:
- Sans (default): `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif`
- Mono (data, codes, IDs): `'SF Mono', 'Roboto Mono', Consolas, monospace`
- Serif (reserved for narrative hero only, optional): `Georgia, 'Times New Roman', serif`

### Scale

| Use | Size | Weight | Color |
|---|---|---|---|
| Page heading (rare) | 22px | 500 | `text.primary` |
| Section heading | 18px | 500 | `text.primary` |
| Subsection heading | 14px | 500 | `text.primary` |
| Body | 14px | 400 | `text.primary` |
| Supporting / label | 13px | 400 | `text.secondary` |
| Metadata / caption | 11px | 500 | `text.tertiary` (often uppercase + 1.2px letter-spacing) |
| Data value (large) | 22px | 500 | semantic color (`risk.*Text` or `text.primary`) |
| Data value (inline) | 13px | 500 | semantic color |
| Mono (incident IDs, codes) | 12px | 400 | `text.tertiary` |

### Rules

- Two weights only: 400 regular, 500 medium. No bold (700+).
- Sentence case for labels and headings. Not Title Case. Not ALL CAPS — except small metadata labels (11px) which use uppercase + letter-spacing as a stylistic device.
- Line-height: 1.5 for body, 1.3 for headings, 1.65 for narrative hero prose.

---

## 5. Spacing scale

4px base unit. Use ONLY these values:

| Token | px |
|---|---|
| `space.xs` | 4 |
| `space.sm` | 8 |
| `space.md` | 12 |
| `space.lg` | 16 |
| `space.xl` | 24 |
| `space.xxl` | 32 |

Component padding defaults:
- Cards: `16px 20px`
- Pills / badges: `4px 10px`
- Buttons: `8px 16px`
- Drill-down sections: `20px 24px`
- Table rows: `14px 16px`
- Form inputs: `8px 12px`
- Sidebar sections: `16px` outer, `12px` between fields

---

## 6. Component patterns

### Cards / panels
- `background: bg.surface`
- `border: 1px solid border.subtle`
- `border-radius: 4px` (NOT 8 or 12 — refinery software has tight corners)
- No shadow. Borders carry the separation.
- Hover (if interactive): `background: bg.elevated`

### Metric KPI card (small summary card with one number)
Pattern used for "High risk: 3", "Medium: 2", "Low: 1" style summaries.
- `background: bg.surface`, `border: 1px solid border.subtle`, `border-radius: 4px`
- Padding: `14px 16px`
- Top label: 11px / 500 / `text.tertiary` / uppercase / letter-spacing 1px
- Bottom value: 22px / 500 / semantic color (`risk.highText` etc.) or `text.primary` for neutral counts
- Bottom value sits 6px below the label
- Layout in a CSS grid: `grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px;`

### Pills / badges
- `padding: 4px 10px`
- `border-radius: 2px` (square, NOT pill-shaped)
- `font-size: 10px`
- `letter-spacing: 1px`
- `text-transform: uppercase`
- For risk pills: solid background with `text.inverse` foreground
- For source-agency badges (BSEE / CSB): `background: bg.elevated`, `border: 1px solid border.subtle`, `color: text.secondary`. Plain agency name, no icon.

### Buttons
- Primary: `background: accent.primary`, `color: text.inverse`, hover `accent.hover`, active `accent.active`
- Secondary: transparent background, `border: 1px solid border.default`, `color: text.secondary`, hover `background: bg.elevated` and `color: text.primary`
- Disabled: 50% opacity, no hover state
- Padding: `8px 16px`
- Border-radius: 4px
- Focus: `box-shadow: shadow.focus`
- No icons unless functional. No emoji.

### Form inputs (text, select, textarea)
- Height: 36px for single-line inputs
- `background: bg.elevated`
- `border: 1px solid border.default`
- `border-radius: 4px`
- `color: text.primary`
- Placeholder: `text.tertiary`
- Padding: `8px 12px`
- Focus: `border-color: accent.primary`, `box-shadow: shadow.focus`
- Disabled: 50% opacity, `cursor: not-allowed`
- Error state: `border-color: risk.high`, error text below in 11px / `risk.highText`
- Select dropdown chevron: 12px stroke `text.tertiary`, no custom icon — let native rendering through with an inline SVG override only if cross-browser inconsistency surfaces

### Tables / lists
- Row borders: `border-bottom: 1px solid border.subtle`
- Hover row: `background: bg.elevated`
- Header row: `text.tertiary`, 11px, uppercase, letter-spacing 1px
- Right-align numeric columns. Left-align text.
- Header padding: `12px 16px`
- Body row padding: `14px 16px`

### Risk indicators (the single most important pattern)
Every barrier prediction shows three redundant signals:
1. A **left-edge risk band** (4px wide) on its container — colored by `risk.high`/`medium`/`low`
2. A **right-side pill** with risk level text — `HIGH` / `MED` / `LOW` / `?`
3. A **probability value** in `risk.*Text` color, formatted to 2 decimals (e.g., `0.82`)

This rule applies to dashboard chrome (ranked-barrier list rows, drill-down headers, KPI summaries). The bowtie SVG interior follows BowTieXP convention — see Section 7 — which already includes a left-edge risk band on barriers. Both patterns are aligned by intent; do not refactor BowtieSVG to match.

### Probability formatting
- Always 2 decimals: `0.82`, not `0.8154` or `82%`
- Inline in dashboard chrome: 13px / 500 / `risk.*Text`
- Large display in drill-down badge: 22px / 500 / `risk.*Text`
- In bowtie metric block (white SVG context): keep existing red/blue convention per Section 7

### SHAP value rendering
- Positive SHAP (pushes risk UP): use `risk.highText` (`#E74C3C`) on dark surfaces, existing `#C62828` inside the bowtie SVG metric block (Section 7 exemption)
- Negative SHAP (pushes risk DOWN): use `accent.primary` (`#2C5F7F`) on dark surfaces, existing `#1565C0` inside the bowtie SVG metric block
- Display name from `getFeatureDisplayName()` — fallback to raw feature name if empty
- Format: `+0.46` for positive (with leading `+`), `-0.18` for negative
- Sort top reasons by absolute value descending — biggest contributor first

### Charts (Recharts)
- Background: transparent — let `bg.surface` show through
- Axis labels: `tick={{ fill: '#6B7280', fontSize: 11 }}` (`text.tertiary`)
- Axis lines: `stroke="#1F2937"` (`border.subtle`)
- Grid lines: `stroke="#1F2937"`, `strokeDasharray="3 3"`, `strokeWidth={0.5}`
- Tooltip: `contentStyle={{ background: '#151B24', border: '1px solid #2A3442', borderRadius: 4, color: '#E8E8E8' }}`
- Single-series default color: `accent.primary` (`#2C5F7F`)
- Two-series: `accent.primary` + `risk.medium` (`#996515`)
- Three+ series: stop and ask before adding — there's almost always a way to split into multiple charts
- Bar fills: solid colors only, no gradients
- Line strokes: 2px

### Expanded row panels

When a row in a table or ranked list expands to show drill-in content inline (not in the side drill-down drawer):
- `background: bg.elevated` (`#1C2430`) — matches hover/elevated surface
- `border-top: 1px solid border.subtle` to separate from the row header
- Padding: `16px 20px`
- Inner content follows the standard drill-down section pattern

### Model / variant KPI cards

Multi-model comparisons (e.g., model1 vs model2 KPIs) use a single accent family. Distinction is carried by:
- Card title text (e.g., "Cascading model" vs "Human factors model")
- Metric values themselves

Do NOT introduce a second accent color to distinguish cards. Left-edge accent band on all model cards: `accent.primary`. If additional visual separation is truly needed: one card uses `accent.primary`, the other uses `border.strong` (neutral gray) — never a new color family.

### Dial / gauge indicators (large semantic visuals)

For larger-than-chip semantic visualizations (risk posture dials, coverage gauges, status rings):
- `background: bg.accent` (`#1A2332`) — neutral dark backdrop
- `border: 2px solid` using the appropriate `risk.*` or `accent.primary` token based on state
- Text inside: matching `risk.*Text` or `text.primary`
- Do NOT use alpha color overlays (`bg-red-500/20` pattern is forbidden here — that's chip allowlist only)
- Do NOT use Tailwind `ring-*` utilities — borders do the work

The chip allowlist (§3) extends to small labels only. Large visual indicators must use tokens.

### Status dots

Small circular status markers (typically 8–12px) use solid semantic backgrounds:
- Success / low → `risk.low` (`#1F6F43`)
- Warning / medium → `risk.medium` (`#996515`)
- Danger / high → `risk.high` (`#C0392B`)
- Unknown → `risk.unknown` (`#4A5568`)

Solid colors, no alpha, no Tailwind utility classes. Per §6 risk pill convention.

### Disabled states (clarification)

Any interactive element (buttons, inputs, side toggles, checkboxes) in disabled state:
- Retains its base token color
- Gets `opacity: 0.5`
- `cursor: not-allowed`
- No hover state fires

Do not introduce lighter-tone variants (`bg-blue-400` style). Opacity is the mechanism.

### Risk tier thresholds — D006 wins

The dashboard's HIGH / MEDIUM / LOW pills are computed from D006 thresholds defined in `configs/risk_thresholds.json`:

- **LOW**: probability < 0.45
- **MEDIUM**: 0.45 ≤ probability < 0.70
- **HIGH**: probability ≥ 0.70

These thresholds are loaded by `src/modeling/cascading/predict.py` and applied to every prediction returned by `/predict-cascading` and `/explain-cascading`.

The cascade model's metadata file (`xgb_cascade_y_fail_metadata.json`) contains a `risk_tier_thresholds` field with different values (HIGH 0.66, MEDIUM 0.33, LOW 0.33). **This field is currently unused** — `predict.py` ignores it and reads `configs/risk_thresholds.json` instead. If the metadata thresholds need to apply, that's a code change (not a UI-CONTEXT.md change). For M003, treat D006 as the only threshold source.

If the discrepancy is ever resolved (either the metadata field is removed or `predict.py` is changed to use it), update this section.

---

## 7. The bowtie diagram is the protected anchor of the product

The bowtie SVG (`frontend/components/diagram/BowtieSVG.tsx`) is the most important visual artifact in the product. It is the single piece of UI that:

- Process safety experts (Fidel, peers) immediately recognize as legitimate domain language
- Translates abstract ML predictions into a domain-native picture
- Makes the entire dashboard credible

### Protection rules — non-negotiable

Every T-task MUST treat the bowtie as a protected artifact:

- **Never simplify, abstract, or replace it.** No "modernized" version, no React-Flow rewrite, no flattened layout.
- **Never reduce its visual fidelity to BowTieXP convention.** The current visual language (gray canvas, blue threats, red consequences, orange-red top event circle, yellow-black hazard banner, white barrier boxes with risk-colored left bands, black pathway lines, gray cylinder connector tabs) is correct and must be preserved.
- **Never override its dimensions to fit other layout demands.** The dashboard layout works around the bowtie's footprint, not the other way around. If a panel wants more space, it shrinks; the bowtie does not.
- **Never hide it behind a tab, modal, or collapsed section.** It is always visible on the main canvas.
- **Never shrink it below readable scale** (minimum 1200px wide on desktop, scaled gracefully below that on smaller viewports — see Section 8 viewport handling).

### Improvement is encouraged

- Better text wrapping
- Cleaner alignment of pathway lines
- Crisper connector tabs
- More legible labels
- Smoother hover/click affordances
- Faster render performance

### Forbidden changes (STOP and ask user)

If a brief asks for any of the following, CCCLI MUST stop and ask the user before proceeding:

- Replacing BowtieSVG with a different diagram library
- Changing the BowTieXP color convention (threats not blue, consequences not red, etc.)
- Removing the metric block under barriers
- Removing the risk-colored left band on barrier boxes
- Removing the connector tab gradients
- Changing pathway line geometry beyond the existing straight-line rendering

### Visual island principle

The bowtie SVG is rendered on its industry-standard gray canvas (`#E0E0E0`). The dashboard chrome around it is dark (`bg.base = #0F1419`). This contrast is intentional — the bowtie reads as a separate, recognized domain artifact embedded in the analytics view. The dark dashboard frames it; it does not absorb it.

The metric block under each barrier (white rect with blue label text and red/blue SHAP values) stays white-on-gray. Do NOT dark-theme the metric block — it is bowtie interior and follows BowTieXP convention.

The only thing that changes around the bowtie in T1+ is the **container wrapper** — the dashboard surface holding the SVG inherits `bg.base`. Everything inside the SVG stays exactly as it is. The container wrapper change (dark `bg.base` around the gray bowtie canvas) shipped in S05a. This rule documents the existing implementation, not a new requirement.

### Grandfathering of S05b changes

The visual changes shipped in S05b — straight pathway lines (S05b/T1), removal of dark lugs from barrier tops (S05b/T3), gradient connector tabs on threats and consequences (S05b/T3), white metric block under barriers with SHAP rows (S05b/T4) — are the **current canonical state** of the bowtie and are protected by this section as much as the original BowTieXP convention. They were the result of a deliberate design pass guided by Fidel's domain feedback and BowTieXP reference comparison. Reverting them is a forbidden change under the rules above.

If a reviewer or future T-task believes one of these changes was wrong, escalate to the user before reverting. Do not silently revert.

### K001 cross-reference

K001 (no automated SVG coordinate changes via CCCLI) is defined in `03_KNOWN_GOTCHAS.md` and applies here. See that file for the canonical statement. This document does not restate K001 to avoid drift between the two sources.

---

## 8. Structural patterns (page layout)

### Main layout
- Page background: `bg.base`
- Three regions: left sidebar, main canvas, optional right drill-down drawer
- No header bar in M003 — the dashboard is the entire page

### Left sidebar (scenario builder)
- Width: 320px collapsed-friendly, 360px default
- `background: bg.surface`
- `border-right: 1px solid border.subtle`
- Sections separated by `border-bottom: 1px solid border.subtle`
- Vertical scroll on overflow (`overflow-y: auto`)
- Section header: 11px / 500 / `text.tertiary` / uppercase / letter-spacing 1px / 16px top padding
- Form fields stacked with 12px gap
- Sticky bottom CTA region for "Analyze Barriers" button — `border-top: 1px solid border.subtle`, padding 16px

### Right drill-down panel
- Width: 420px
- `background: bg.elevated`
- `border-left: 1px solid border.subtle`
- Slides in from right (translateX 100% → 0, 200ms ease-out) when a barrier is clicked
- Closes via close button (top-right) or clicking outside
- Inside: header region with barrier name + risk badge, then tab bar, then scrollable content
- `box-shadow: shadow.drill` if it overlays the canvas (vs pushing it)

### Tab bar (used inside drill-down and at dashboard top-right)
- Height: 36px
- `background: bg.surface` (drill-down) or transparent (dashboard top-right)
- Tab item: 11px / 500 / uppercase / letter-spacing 0.8px / padding `10px 16px`
- Active state: `color: text.primary`, `border-bottom: 2px solid accent.primary`
- Inactive: `color: text.tertiary`, no border
- Hover (inactive): `color: text.secondary`
- No icons in tabs unless absolutely needed
- Tab bar full width, items left-aligned (drill-down) or right-aligned (dashboard top-right)

### Dashboard canvas (main region)
- Background: `bg.base`
- Padding: 24px
- Vertical stack with consistent 24px gap between sections
- Order from top:
  1. Narrative hero (T2 — when present)
  2. KPI summary cards row (3-up grid)
  3. Bowtie SVG (centered, max-width 1800px)
  4. Ranked barriers section
  5. Optional secondary panels (Drivers/HF, Evidence preview)

### Viewport handling and panel collapse

The bowtie has a minimum readable width of 1200px. With sidebar (360px) and drill-down panel (420px) both open on a 1920px viewport, available canvas is 1140px — too narrow.

Resolution rules:

- **Drill-down opens → sidebar auto-collapses to a 48px icon strip.** The sidebar can be re-expanded by clicking the expand icon, but doing so will close the drill-down. Only one expanded auxiliary panel at a time.
- **On viewports below 1600px width** (less common but possible — laptops, projectors): sidebar starts collapsed by default; user must explicitly expand to add barriers.
- **On viewports below 1200px width** (mobile/tablet — out of scope for M003 demo): the dashboard renders a "Best viewed on a desktop monitor" message. Do NOT spend time making the bowtie responsive below 1200px in M003.
- **The bowtie always gets full available width up to 1800px.** It does not shrink to give other panels more space.

This is the only place in the doc where the layout *responds to* viewport width — the rest of the design assumes desktop monitor (≥1600px).

---

## 9. Narrative hero (T2 spec)

The product's front door. Composed client-side from cascading predictions + RAG evidence. Three sentences max.

- Position: top of the dashboard canvas, above the KPI cards
- Width: full width of canvas (minus 24px padding)
- `background: bg.accent` (`#1A2332`)
- `border-left: 3px solid risk.high` (`#C0392B`) — left accent bar
- `border-radius: 0 4px 4px 0` so the accent bar reads as one block with the surface
- Padding: `20px 24px`
- Inside structure:
  - Top metadata label: 13px / 400 / `text.secondary` — e.g., "System narrative"
  - Body text: 16px / 400 / `text.primary` / line-height 1.65 — three sentences with inline emphasis on numbers and entity names (use `font-weight: 500` for emphasis, NOT a different color)
  - Inline links to drill-downs: `accent.primary`, dotted underline, cursor pointer

When NOT to render the hero:
- Before user clicks Analyze (no predictions yet) → render a placeholder strip with `text.tertiary` text: "Click Analyze Barriers to generate scenario summary."

### Composition strategy (T2 split)

The hero has two composition paths:

**T2a — Template (default, always-on):**
Client-side composition from cascading predictions + RAG stats already in state. Renders instantly on Analyze. Deterministic, testable, zero LLM cost. This is the baseline narrative the user always sees.

Composition logic:
- Count barriers, count high-risk, identify top-1 by `average_cascading_probability`
- Pull retrieval stats: `similarIncidentsCount` (count of RAG-retrieved evidence snippets for the selected target barrier), `totalRetrievedIncidents` (fixed constant = RAG corpus size = 156)
- Template: "This scenario has {N} barriers defending against {top_event}. {high_risk_count} are high-risk. The weakest link is {top_barrier} — historical data shows similar barriers failed in {similar_incident_count} of {total_retrieved} comparable incidents."
- Edge cases documented in `NarrativeHero.tsx::composeNarrative`

**T2b — Haiku synthesis (opt-in button):**
Server endpoint `POST /narrative-synthesis` accepts top barrier + SHAP top-3 + 3 RAG incident contexts. Returns a 2-3 sentence narrative synthesizing the *why* of the risk pattern. Rendered behind a "✨ Summarize with AI" button at the hero's top-right corner. Clicking the button replaces the template body with the synthesis. Separate commit (T2b).

Rationale for the split: the template is deterministic and fast (factual aggregate — the *what*). The LLM adds interpretive prose from RAG evidence (the *why*) but costs latency, determinism, and a dependency on Anthropic's API. Making it opt-in via button lets the user pay the cost of interpretation when they want it, while keeping the always-on hero free and reliable.

---

## 10. Provenance / trust strip

A persistent small strip showing model and data lineage. Builds Fidel-credibility and addresses the domain-expert concern that "I don't know what's ML and what's typed in."

### Position and styling
- Position: bottom of dashboard canvas, full-width
- Background: `bg.surface`
- Border: `1px solid border.subtle`
- Border-radius: 4px
- Padding: `12px 16px`
- Inner layout: vertical stack, `gap: 4px` between Line 1 and Line 2
- Line text: 11px / 400 / `text.tertiary` / line-height 1.4
- Right-side link "View model card →" floats right (M003: rendered greyed-out and non-clickable until M004 ships the model card view; cursor: default; opacity 0.5)

### Content — two lines, exactly as written

Line 1 (predictions provenance):
```
Predictions: XGBoost cascade · 813 rows from 156 BSEE+CSB incidents · 5-fold CV AUC 0.76 ± 0.07
```

Line 2 (evidence provenance):
```
Evidence: hybrid RAG · 1,161 barriers · 156 incidents · 4-stage retrieval
```

### Source-agency distribution (factual reference, not displayed in chrome)

Of the 156 incidents the model knows about: **113 are from BSEE** (Bureau of Safety and Environmental Enforcement, US offshore oil and gas), **43 are from CSB** (US Chemical Safety Board, onshore process incidents). The dashboard does not display this split inline (would clutter the strip), but it is available in the model card detail view.

### Source of truth for the numbers

These numbers are NOT placeholder text. They come from real artifacts on disk:

- **Model training rows (813)** → `data/models/artifacts/xgb_cascade_y_fail_metadata.json` field `training_rows`
- **Unique incidents (156)** → `data/processed/cascading_training.parquet` unique `incident_id` count (matches RAG corpus)
- **Model AUC (0.76 ± 0.07)** → same metadata file, `cv_scores.mean` and `cv_scores.std`
- **Source agencies + counts (BSEE 113 / CSB 43)** → `data/models/cascading_input/barrier_model_dataset_base_v3.csv` field `source_agency` grouped by `incident_id`
- **RAG barrier corpus (1,161)** → `data/rag/v2/datasets/barrier_documents.csv` row count
- **RAG incident corpus (156)** → `data/rag/v2/datasets/incident_documents.csv` row count

### Important: parquet is newer than model

The latest `cascading_training.parquet` has 530 rows (after dedup/filtering done after model training). The model itself was trained on the 813-row snapshot referenced in its metadata. **Always cite the model metadata for "what the model was trained on" — not the latest parquet.** If the model is retrained, both will realign.

---

## 11. Empty / loading / error states

### Empty states
- Centered text in the empty container
- Style: 13px / 400 / `text.tertiary`
- Sentence case, single sentence, no exclamation marks
- No illustration, no icon
- Examples:
  - "Click Analyze Barriers to generate predictions."
  - "No similar incidents found for this barrier."
  - "Add at least one barrier to begin."

### Loading states
- For data fetches (Analyze, Explain, etc.): subtle pulse on the loading region
  - `animation: pulse 1.5s ease-in-out infinite`
  - `color: text.tertiary`, 13px
  - Text examples: "Analyzing barriers...", "Loading evidence..."
- For region/skeleton loading: `background: bg.surface` blocks at the dimensions of the eventual content. No shimmer animation. Static gray blocks.
- For inline spinners (rare — only when exact text doesn't make sense):
  - 14px circle, `border: 2px solid border.subtle`, `border-top-color: accent.primary`
  - `animation: spin 0.8s linear infinite`

### Error states
- Inline error text: 11px / 400 / `risk.highText`
- Error toast / alert region: `background: bg.surface`, `border-left: 3px solid risk.high`, padding `12px 16px`, content 13px / `text.primary`
- No emoji icons in errors. Optional 14×14 SVG warning icon in `risk.highText` if needed
- Error state is recoverable — always include a "Retry" or "Dismiss" button when the user can act

---

## 12. Animation and motion

- Maximum animation duration: 200ms
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)` (ease-out) for entrances, `cubic-bezier(0.4, 0, 1, 1)` (ease-in) for exits
- Allowed animations:
  - Drawer slide (200ms ease-out)
  - Hover state transitions on background/border colors (150ms)
  - Focus ring fade-in (100ms)
  - Loading pulse (1.5s loop, see Section 11)
  - Spinner rotation (0.8s loop)
- Forbidden:
  - Bounce easings, spring physics
  - Animations longer than 200ms
  - Page transition animations
  - Auto-scrolling
  - Auto-playing video / GIF
  - Parallax scrolling
  - Marquee, ticker, or any horizontal-scrolling text

---

## 13. Forbidden patterns (visual + interaction)

### Visual
- No glassmorphism, claymorphism, neumorphism, brutalism, bento grids
- No gradients (except the existing BowtieSVG connector tab)
- No drop shadows, blur, glow, neon
- No background images, patterns, textures
- No animated gradients or "shimmer" loading states
- No hero illustrations, mascots, character art
- No "card stacks" with z-index pseudo-3D

### Interaction
- No carousels
- No modals where a drawer or inline panel would do
- No "click to reveal" hidden content (process engineers want everything visible)
- No tooltips for critical information — if it matters, it's on screen
- No required onboarding flow
- No progress bars unless an actual operation is running
- No auto-suggest dropdowns that obscure other content
- No infinite scroll — paginate or expand-on-click

---

## 14. Mode handling

**M003 is dark-only.** Light mode is explicitly out of scope.

- Do NOT add a light/dark toggle UI
- Do NOT structure tokens as a `dark` and `light` pair
- Do NOT use Tailwind's `dark:` variant — write the dark values as the default
- Do NOT include `prefers-color-scheme` media queries
- If a future milestone (M004+) adds light mode, it will introduce a parallel token map then. For now, simplicity wins.

---

## 15. Update protocol

This document is versioned. Every T-task that introduces a new pattern or token MUST:

1. Update UI-CONTEXT.md in the same commit as the implementation
2. Bump the version number at the top (v2.2 → v2.3 → v3 → ...)
3. Add a "v{N} changelog" line at the bottom: `v3: T2 added narrative hero spec — Section 9.`

If a T-brief asks for something this document forbids (e.g., a tooltip, a gradient, a teal accent), CCCLI must STOP and ask the user — not silently follow the brief.

If a design need arises that this document doesn't cover, CCCLI proposes a token/pattern addition rather than inventing freely. The proposal goes in the brief response, the user approves, then the change goes into the next commit's UI-CONTEXT.md update.

---

## 16. How CCCLI uses this file

Every UI brief includes the line: *"Read UI-CONTEXT.md before writing any code. Apply tokens, patterns, and forbidden lists. Reference Section X for [specific component]."*

Workflow per brief:
1. Read UI-CONTEXT.md fully
2. Read the brief
3. If brief requests something forbidden or undefined: STOP, propose, await user
4. Implement using tokens from `frontend/lib/design-tokens.ts`
5. Verify in browser via Playwright MCP screenshot
6. Update UI-CONTEXT.md if new patterns introduced (Section 15)
7. Commit

---

## Changelog

- v1: initial draft (philosophy, palette, typography, spacing, basic components, bowtie exemption)
- v2: closed 18 gaps from team review — added form inputs, sidebar/drawer/tab specs, KPI card pattern, source-agency badges, SHAP rendering, narrative hero, provenance strip, empty/loading/error states, animation rules, dark-only mode, update protocol, Tailwind allowlist exception, Recharts wiring
- v2.1: factual corrections — Section 7 rewritten as "protected anchor" framing with forbidden-changes list; Section 10 provenance string corrected with two-line predictions+evidence format
- v2.2: closed 13 gaps from v2.1 red-team — verified all data-truth numbers against disk artifacts; resolved 530-vs-813 row discrepancy (model metadata is the truth, not latest parquet); documented BSEE 113 / CSB 43 incident split; resolved D006-vs-cascade-metadata threshold conflict (D006 wins by code, metadata field unused); added viewport sizing rules with sidebar auto-collapse on drill-down; added S05b changes grandfathering; fixed K001 cross-doc coupling; explicitly scoped Tailwind allowlist to chip-style elements only (standalone text-color utilities go through tokens)
- v2.3: T1 soul pass execution — added expanded row panel pattern, model/variant KPI card rule (one accent family), dial/gauge indicator pattern (no alpha overlays on large elements), status dot pattern, disabled state opacity clarification. Swap map holes from v2.2 brief resolved inline during T1 execution.
- v2.4: T2a ships template-path narrative hero. §9 amended with T2a/T2b composition split — template always-on, Haiku synthesis behind opt-in button (T2b).
