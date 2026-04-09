# Sprint 4: Visual Polish & Final Touches

**Goal:** Every surface feels intentional and professional. No raw internal labels, no cramped layouts, no unexplained numbers. A process safety engineer opens this and thinks "this team knows what they're doing."

**Time estimate:** 2-3 hours  
**Depends on:** Sprints 1-3 complete

---

## Task 1: Consolidate Two Barrier Forms into One

**File:** `frontend/components/sidebar/BarrierForm.tsx`

**Current problem:** The sidebar has two identical form sections — "Add Prevention Barrier" and "Add Mitigation Barrier" — with the exact same fields (name, type, family, role, LOD). This wastes vertical space and forces users to scroll past the first form to reach the second.

**What to change:**

Merge into a single form with a Prevention/Mitigation toggle at the top:

```tsx
<div className="mb-4">
  <h3 className="text-sm font-semibold text-[#E8ECF4] mb-2">Add Barrier</h3>
  
  {/* Side toggle */}
  <div className="flex rounded-lg overflow-hidden border border-[#2E3348] mb-3">
    <button
      onClick={() => setSide('prevention')}
      className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
        side === 'prevention'
          ? 'bg-blue-600 text-white'
          : 'bg-[#242836] text-[#5A6178] hover:text-[#8B93A8]'
      }`}
    >
      Prevention
    </button>
    <button
      onClick={() => setSide('mitigation')}
      className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
        side === 'mitigation'
          ? 'bg-blue-600 text-white'
          : 'bg-[#242836] text-[#5A6178] hover:text-[#8B93A8]'
      }`}
    >
      Mitigation
    </button>
  </div>
  
  {/* Single form: name, type, family, role, LOD */}
  {/* ... same fields as before ... */}
  
  <button className="w-full bg-blue-600 ...">
    + Add {side === 'prevention' ? 'Prevention' : 'Mitigation'} Barrier
  </button>
</div>
```

This saves ~200px of vertical space and puts all the important content (barrier list, human factors, Analyze button) closer to the top of the viewport.

---

## Task 2: Fix Barrier List Truncation in Sidebar

**File:** `frontend/components/sidebar/BarrierForm.tsx` (or wherever the barrier list is rendered)

**Current problem:** Barrier names truncate with "..." ("Operator Pre-transfer Ch...") and the trash/delete icon is always visible, eating space.

**What to change:**

- Show the full barrier name (wrap to 2 lines if needed instead of truncating)
- Hide the delete icon by default, show on hover only
- Risk badge should be a small dot (8px) not the word "Low"

```tsx
{barriers.map((b) => (
  <div
    key={b.id}
    className="group flex items-start gap-2 py-1.5 px-2 rounded hover:bg-[#242836] cursor-pointer transition-colors"
    onClick={() => setSelectedBarrierId(b.id)}
  >
    {/* Risk dot */}
    <span
      className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
        b.riskLevel === 'red' ? 'bg-red-500'
        : b.riskLevel === 'amber' ? 'bg-amber-400'
        : b.riskLevel === 'green' ? 'bg-green-500'
        : 'bg-[#5A6178]'
      }`}
    />
    
    {/* Barrier name — allow wrapping */}
    <span className="text-xs text-[#E8ECF4] leading-tight flex-1">
      {b.name}
    </span>
    
    {/* Side indicator */}
    <span className="text-[10px] text-[#5A6178] flex-shrink-0 mt-0.5">
      {b.side === 'prevention' ? 'P' : 'M'}
    </span>
    
    {/* Delete — hover only */}
    <button
      className="opacity-0 group-hover:opacity-100 text-[#5A6178] hover:text-red-400 transition-opacity"
      onClick={(e) => { e.stopPropagation(); removeBarrier(b.id) }}
    >
      <svg width="12" height="12" viewBox="0 0 12 12">
        <path d="M9 3L3 9M3 3l6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    </button>
  </div>
))}
```

---

## Task 3: Redesign Executive Summary Top Section

**File:** `frontend/components/dashboard/DashboardView.tsx` and related components

**Current problem:** The Executive Summary leads with a Risk Distribution bar chart that just shows a single green bar (all Low). There's no tension, no insight, no story.

**What to change:**

Replace the current layout with a 2-column grid at the top:

**Left column: Scenario Risk Posture (new)**
```tsx
<div className="bg-[#242836] rounded-lg p-5 border border-[#2E3348]">
  <h3 className="text-sm font-medium text-[#5A6178] mb-3 uppercase tracking-wider">
    Scenario Risk Posture
  </h3>
  <div className="flex items-center gap-4">
    {/* Large risk indicator */}
    <div className={`w-16 h-16 rounded-full flex items-center justify-center text-lg font-bold ${
      overallRisk === 'high' ? 'bg-red-500/20 text-red-400 ring-2 ring-red-500/40'
      : overallRisk === 'medium' ? 'bg-amber-500/20 text-amber-400 ring-2 ring-amber-500/40'
      : 'bg-green-500/20 text-green-400 ring-2 ring-green-500/40'
    }`}>
      {overallRisk === 'high' ? 'H' : overallRisk === 'medium' ? 'M' : 'L'}
    </div>
    <div>
      <p className="text-base font-semibold text-[#E8ECF4]">
        {overallRisk === 'high' ? 'High Risk' : overallRisk === 'medium' ? 'Elevated Risk' : 'Controlled Risk'}
      </p>
      <p className="text-xs text-[#5A6178] mt-0.5">
        {counts.high} high · {counts.medium} medium · {counts.low} low risk barriers
      </p>
    </div>
  </div>
</div>
```

**Right column: Quick Stats**
```tsx
<div className="bg-[#242836] rounded-lg p-5 border border-[#2E3348]">
  <h3 className="text-sm font-medium text-[#5A6178] mb-3 uppercase tracking-wider">
    Analysis Overview
  </h3>
  <div className="grid grid-cols-2 gap-3">
    <div>
      <p className="text-2xl font-bold text-[#E8ECF4]">{barriers.length}</p>
      <p className="text-xs text-[#5A6178]">Barriers analyzed</p>
    </div>
    <div>
      <p className="text-2xl font-bold text-[#E8ECF4]">
        {barriers.filter(b => b.side === 'prevention').length} / {barriers.filter(b => b.side === 'mitigation').length}
      </p>
      <p className="text-xs text-[#5A6178]">Prevention / Mitigation</p>
    </div>
    <div>
      <p className="text-2xl font-bold text-[#E8ECF4]">174</p>
      <p className="text-xs text-[#5A6178]">Reference incidents</p>
    </div>
    <div>
      <p className="text-2xl font-bold text-[#E8ECF4]">558</p>
      <p className="text-xs text-[#5A6178]">Barrier observations</p>
    </div>
  </div>
</div>
```

Keep the Risk Distribution chart below this as a secondary element, but render it as a compact horizontal bar (not tall).

---

## Task 4: Improve Scenario Context Display

**File:** `frontend/components/dashboard/ScenarioContext.tsx`

**Current state:** Shows "Loss of containment during high-pressure gas transfer operations" with tiny badges "5 barriers · 5 analyzed". This is the WHAT of the entire analysis — it should be prominent.

**What to change:**

Move Scenario Context to the TOP of the Executive Summary (above the risk posture). Style it as a page header:

```tsx
<div className="mb-6">
  <p className="text-xs text-[#5A6178] uppercase tracking-wider mb-1">
    Top Event / Scenario
  </p>
  <h2 className="text-xl font-semibold text-[#E8ECF4]">
    {eventDescription}
  </h2>
  <div className="flex gap-3 mt-2">
    {/* Threat badges */}
    {threats.map(t => (
      <span key={t.id} className="text-xs px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/30">
        {t.name}
      </span>
    ))}
    {/* Consequence badges */}
    {consequences.map(c => (
      <span key={c.id} className="text-xs px-2 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
        {c.name}
      </span>
    ))}
  </div>
</div>
```

---

## Task 5: Global Style Consistency Pass

**All frontend files**

Quick pass through all components to catch:

1. **Any remaining "A-HW", "ST Socio", "BEH Behavioural" strings** — search and replace with domain terms
2. **Any raw probability/score numbers** shown to users without context — either remove or add labels
3. **Inconsistent border radius** — standardize to `rounded-lg` (8px) for cards, `rounded-md` (6px) for badges
4. **Inconsistent text colors** — ensure hierarchy:
   - Primary text: `text-[#E8ECF4]`
   - Secondary text: `text-[#8B93A8]`
   - Tertiary/disabled: `text-[#5A6178]`
   - Section headers: `text-[#5A6178] uppercase tracking-wider text-xs font-medium`
5. **"New Scenario" button** at the bottom of sidebar — is this functional? If not, remove it.

---

## Task 6: Pathway View Polish

**File:** `frontend/components/diagram/PathwayView.tsx`

**Quick improvements:**

1. The Pathway View cards should use the same risk stripe pattern as the diagram (colored left border)
2. Add the barrier type and LOD as small badges on each card (they're shown in the Ranked Barriers table but not here)
3. Selected card should have a clear visual state (blue border or background shift)

---

## Final Verification Checklist

After ALL sprints complete:

- [ ] Dashboard has 4 tabs, all with real content
- [ ] Executive Summary tells a story: scenario → risk posture → top barriers → data basis
- [ ] No raw ML metrics visible to domain experts (F1, MCC, base rate)
- [ ] No system codes visible (A-HW, ST, BEH)
- [ ] Bowtie diagram matches BowTieXP visual language (barriers on pathways, color stripes, blue/red borders)
- [ ] Clicking a barrier opens a detail drawer with SHAP + Evidence + Recommendations
- [ ] Evidence is structured with collapsible sections (not a wall of text)
- [ ] Degradation factors are colored badges
- [ ] All charts have value labels
- [ ] PIF Prevalence chart maxes at 100%
- [ ] Similar Incidents collapsed by default
- [ ] Left sidebar has one consolidated barrier form
- [ ] Barrier list doesn't truncate names
- [ ] All tests pass: `cd frontend && npx vitest run`
- [ ] App works at 1280px minimum width
- [ ] A process safety engineer would look at this and think "professional tool"
