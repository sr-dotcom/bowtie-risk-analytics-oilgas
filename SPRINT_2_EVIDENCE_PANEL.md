# Sprint 2: Evidence & Detail Panel Restructure

**Goal:** The evidence narrative becomes scannable and trustworthy. The detail panel gets room to breathe. Degradation factors become visual, not text dumps.

**Time estimate:** 3-4 hours  
**Depends on:** Sprint 1 complete  
**Validate in browser between each task.**

---

## Task 1: Restructure Evidence Narrative into Collapsible Sections

**File:** `frontend/components/panel/EvidenceSection.tsx` (and the Evidence tab in dashboard)

**Context:** Currently the evidence tab shows a wall of unformatted LLM-generated text. The narrative has internal structure (headers like "## Section 1 — Evidence Narrative", "Recommendations", "Similar Incidents") but it's rendered as a single continuous block.

**What to do:**

Parse the LLM evidence response into structured sections. The `/explain` endpoint returns markdown-formatted text. Split it into sections and render each in its own collapsible card.

**Section structure to detect and render:**

1. **Key Findings** (always visible, never collapsed) — Extract the first 2-3 sentences as a TL;DR summary card at the top. Give it a subtle blue-left-border treatment like an info callout.

2. **Evidence Narrative** (collapsed by default, "Read full analysis" toggle) — The main body text. Render markdown properly (bold, headers). Max visible height ~200px with "Show more" expansion.

3. **Recommendations** (always visible) — These are already rendered as green-bordered cards. Keep this pattern — it's good. Each recommendation gets its own card.

4. **Similar Incidents** (collapsed by default) — Show just incident ID + first sentence as a summary. Expand to see full text. Each incident in an accordion item.

**Implementation approach:**

```tsx
// Parse the evidence text into sections
function parseEvidenceNarrative(text: string) {
  const sections = {
    narrative: '',
    recommendations: [] as string[],
    similarIncidents: [] as { id: string; summary: string; full: string }[],
  }
  // Split on known headers: "Recommendations", "Similar Incidents"
  // Extract each section's content
  return sections
}
```

Use a simple disclosure/accordion pattern. If shadcn/ui Accordion is installed, use it. Otherwise use a `<details>/<summary>` with styled wrapper or a useState toggle.

**Visual treatment:**
- Section headers: `text-sm font-semibold text-[#E8ECF4]` with bottom border
- Collapsed state: shows header + "▶ Show details" in `text-[#5A6178]`
- Expanded state: smooth max-height transition
- Key Findings card: `bg-[#1A2332] border-l-4 border-blue-500 p-4 rounded-r-lg`
- Recommendation cards: keep existing green-left-border pattern
- Similar Incidents: `bg-[#1E2230] rounded-lg p-3` with incident ID as subtitle

**Why:** Nobody reads walls of text. Structure creates trust. The user should get the answer in 5 seconds (Key Findings), then optionally drill deeper.

---

## Task 2: Convert Right Sidebar to Slide-Out Drawer

**File:** `frontend/components/BowtieApp.tsx` + create new `frontend/components/panel/DetailDrawer.tsx`

**Context:** The current right sidebar is a fixed 384px (`w-96`) panel that's always visible. This cramps SHAP waterfall charts and wastes space when no barrier is selected.

**What to do:**

Replace the fixed `<aside>` right panel with a slide-out drawer that:
- Opens when a barrier is clicked (selectedBarrierId is set)
- Closes on Escape key, clicking outside, or clicking an X button
- Is 560px wide (`w-[560px]`)
- Slides in from the right with a transition
- Has a semi-transparent backdrop that dims the diagram behind it

**Implementation:**

Create `DetailDrawer.tsx`:
```tsx
'use client'

import { useEffect, useRef } from 'react'
import { useBowtieContext } from '@/context/BowtieContext'
import DetailPanel from './DetailPanel'

export default function DetailDrawer() {
  const { selectedBarrierId, setSelectedBarrierId } = useBowtieContext()
  const drawerRef = useRef<HTMLDivElement>(null)
  const isOpen = !!selectedBarrierId

  // Close on Escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedBarrierId(null)
    }
    if (isOpen) document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [isOpen, setSelectedBarrierId])

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 transition-opacity"
          onClick={() => setSelectedBarrierId(null)}
        />
      )}
      {/* Drawer */}
      <div
        ref={drawerRef}
        className={`fixed top-0 right-0 z-40 h-full w-[560px] bg-[#1A1D27] border-l border-[#2E3348] 
          transform transition-transform duration-200 ease-out overflow-y-auto
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Close button */}
        <button
          onClick={() => setSelectedBarrierId(null)}
          className="absolute top-3 right-3 z-50 text-[#5A6178] hover:text-[#E8ECF4] transition-colors"
          aria-label="Close detail panel"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M15 5L5 15M5 5l10 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>
        
        {isOpen && (
          <div className="p-5 pt-10">
            <DetailPanel />
          </div>
        )}
      </div>
    </>
  )
}
```

**In BowtieApp.tsx:**
- Remove the fixed `<aside className="w-96 ...">` right panel
- Import and add `<DetailDrawer />` inside the main layout (after `</main>`)
- The main content area (`<main>`) now takes full remaining width: `flex-1`

**Why:** 
- SHAP waterfalls get 560px instead of 384px — readable labels, proper proportions
- The bowtie diagram gets more canvas space by default
- Click-to-open is more intentional than always-showing an empty panel
- Escape-to-close is standard drawer UX (think Figma, Linear, Notion)

---

## Task 3: Replace Degradation Factor Text Dump with Badges

**File:** `frontend/components/panel/DetailPanel.tsx` (the Overview tab content)

**Context:** Currently degradation factors are shown as a comma-separated string: "Situational Awareness Loss, Communication Breakdown, Procedural Failure". These are the answer to "WHY did this barrier fail?" — they deserve more visual weight.

**What to do:**

Find where degradation_factors are rendered (likely as a `<p>` with comma-joined text). Replace with badge/chip components:

```tsx
{/* Degradation Factors */}
{pred.degradation_factors && pred.degradation_factors.length > 0 && (
  <div className="mt-4">
    <h4 className="text-xs font-medium text-[#5A6178] mb-2 uppercase tracking-wider">
      Degradation Factors
    </h4>
    <div className="flex flex-wrap gap-1.5">
      {pred.degradation_factors.map((df, i) => (
        <span
          key={i}
          className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium
            ${df.strength === 'strong' 
              ? 'bg-red-500/15 text-red-400 border border-red-500/30' 
              : df.strength === 'moderate'
              ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
              : 'bg-blue-500/15 text-blue-400 border border-blue-500/30'
            }`}
        >
          {df.name}
          {df.strength && (
            <span className="ml-1.5 opacity-70 text-[10px]">
              ({df.strength})
            </span>
          )}
        </span>
      ))}
    </div>
  </div>
)}
```

Color-code by strength: strong = red-tinted, moderate = amber-tinted, weak = blue-tinted. This immediately tells the user which factors matter most.

**Why:** These factors are the core analytical insight — "here's WHY this barrier is unreliable." A comma-separated string buries the answer. Colored badges make it scannable in 1 second.

---

## Task 4: Add Plain-Language Risk Summary to Detail Panel

**File:** `frontend/components/panel/DetailPanel.tsx` (Overview tab)

**Context:** Currently the Overview tab shows "Low reliability concern / Historical reliability assessment" with a green badge, then jumps straight into "Barrier Analysis Factors" with "Base rate: 1.747". The number 1.747 means nothing to a safety engineer.

**What to do:**

Add a plain-language summary between the risk badge and the SHAP analysis. This summary should be derived from the data:

```tsx
{/* Risk Summary — plain language */}
<div className="mt-3 bg-[#0F1117] rounded-lg p-3">
  <p className="text-sm text-[#8B93A8] leading-relaxed">
    {riskLevel === 'green' && (
      <>This barrier has demonstrated <span className="text-green-400 font-medium">historically low failure rates</span> across similar operational contexts in the BSEE/CSB incident database.</>
    )}
    {riskLevel === 'amber' && (
      <>This barrier shows <span className="text-amber-400 font-medium">mixed historical reliability</span> — some similar barriers have failed under comparable conditions.</>
    )}
    {riskLevel === 'red' && (
      <>This barrier has <span className="text-red-400 font-medium">significant historical failure patterns</span> in similar operational contexts. Priority review recommended.</>
    )}
    {' '}Top contributing factor: <span className="text-[#E8ECF4] font-medium">{topShapFeatureName}</span>.
  </p>
</div>
```

Also **remove or relabel "Base rate: 1.747"** — change it to something meaningful. The base rate is the model's average log-odds prediction before SHAP adjustments. Instead of showing the raw number, either remove it or show:
```
Model baseline (avg. across all barriers): 1.747
```
in smaller `text-xs text-[#5A6178]` text.

**Why:** Every number on screen should answer a question the user has. "Base rate: 1.747" answers no question. A plain-language summary answers "should I worry about this barrier?"

---

## Verification Checklist

After completing all tasks, verify in browser:

- [ ] Clicking a barrier opens a 560px drawer from the right (not a fixed sidebar)
- [ ] Pressing Escape closes the drawer
- [ ] Clicking the backdrop closes the drawer
- [ ] SHAP waterfall chart has readable labels at 560px width
- [ ] Degradation factors show as colored badges (red/amber/blue by strength)
- [ ] Evidence narrative is split into collapsible sections
- [ ] "Key Findings" is always visible at top of evidence
- [ ] Similar Incidents are collapsed by default
- [ ] Recommendations still show as green-bordered cards
- [ ] Plain-language risk summary appears in Overview tab
- [ ] "Base rate" number is either removed or contextualized
- [ ] Bowtie diagram has more horizontal space now (no fixed right panel)
- [ ] Run tests: `cd frontend && npx vitest run`
