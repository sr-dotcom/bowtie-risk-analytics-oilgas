# Sprint 1: Quick Wins — Remove the "Unfinished" Impression

**Goal:** Every screen a user can reach should look complete and intentional. No empty tabs, no broken charts, no raw ML metrics shown to domain experts.

**Time estimate:** 2-3 hours  
**Validate in browser between each task.**

---

## Task 1: Remove Empty Tabs from Dashboard

**File:** `frontend/components/dashboard/DashboardView.tsx`

**What to do:**
Remove `barrier-coverage`, `incident-trends`, and `risk-matrix` from the `TABS` array. These currently show "coming soon" placeholders — they destroy credibility when a domain expert clicks through.

Change the TABS constant from 7 tabs to 4:

```ts
const TABS = [
  { id: 'executive-summary', label: 'Executive Summary' },
  { id: 'drivers-hf', label: 'Drivers & Human Factors' },
  { id: 'ranked-barriers', label: 'Ranked Barriers' },
  { id: 'evidence', label: 'Evidence' },
] as const
```

Also remove the fallback "coming soon" `<div>` in the tab content rendering section (the block that renders when `activeTab` doesn't match any known tab).

**Why:** Three blank "coming soon" pages in a demo = three moments of "this isn't finished."

---

## Task 2: Fix PIF Prevalence Chart Scale Bug

**File:** `frontend/components/dashboard/DriversHF.tsx`

**What to do:**
The PIF Prevalence horizontal bar chart's X-axis currently auto-scales to 400% which is clearly wrong — prevalence is a 0-to-1 ratio (0% to 100%). 

Find the `<XAxis>` inside `PifPrevalenceChart` (around line 248) and add a `domain` prop:

```tsx
<XAxis
  type="number"
  domain={[0, 1]}
  tickFormatter={(v) => `${((v as number) * 100).toFixed(0)}%`}
  tick={{ fontSize: 12, fill: '#8B93A8' }}
  stroke="#2E3348"
/>
```

The key fix is adding `domain={[0, 1]}` so Recharts doesn't auto-expand the axis.

**Why:** A chart showing 400% for a prevalence metric looks broken. It is broken.

---

## Task 3: Add Value Labels to All Horizontal Bar Charts

**Files:** 
- `frontend/components/dashboard/DriversHF.tsx` (GlobalShapChart + PifPrevalenceChart)
- `frontend/components/dashboard/RiskDistributionChart.tsx`

**What to do:**
Add `<LabelList>` to the `<Bar>` component in each chart to show values at the end of bars. Import `LabelList` from recharts.

For **GlobalShapChart** (the Global Feature Importance chart):
```tsx
<Bar dataKey="importance" isAnimationActive={false}>
  <LabelList
    dataKey="importance"
    position="right"
    formatter={(v: number) => v.toFixed(3)}
    style={{ fontSize: 10, fill: '#8B93A8' }}
  />
  {/* existing Cell mapping */}
</Bar>
```

For **PifPrevalenceChart**:
```tsx
<Bar dataKey="prevalence" isAnimationActive={false}>
  <LabelList
    dataKey="prevalence"
    position="right"
    formatter={(v: number) => `${(v * 100).toFixed(0)}%`}
    style={{ fontSize: 10, fill: '#8B93A8' }}
  />
  {/* existing Cell mapping */}
</Bar>
```

For **RiskDistributionChart**:
```tsx
<Bar dataKey="count" isAnimationActive={false}>
  <LabelList
    dataKey="count"
    position="right"
    style={{ fontSize: 11, fill: '#8B93A8' }}
  />
  {/* existing Cell mapping */}
</Bar>
```

**Why:** Bar charts without value labels force users to estimate by eyeballing axis distance. That's lazy charting.

---

## Task 4: Replace Raw Model KPIs with Data Provenance Card

**File:** `frontend/components/dashboard/DashboardView.tsx` and `frontend/components/dashboard/ModelKPIs.tsx`

**What to do:**
The current ModelKPIs component shows F1=0.928, MCC=0.793, F1=0.348, MCC=0.266 — raw ML metrics that a process safety engineer (Fidel) neither understands nor cares about. Replace it with a "Data Provenance" card that tells the user WHY they should trust the assessment.

**Option A (preferred):** Replace `<ModelKPIs />` in the Executive Summary tab with a new inline card:

In `DashboardView.tsx`, replace:
```tsx
<div className="mt-6">
  <ModelKPIs />
</div>
```

With:
```tsx
<div className="mt-6 bg-[#242836] rounded-lg p-4 border border-[#2E3348]">
  <h3 className="text-sm font-semibold text-[#E8ECF4] mb-2">Assessment Basis</h3>
  <p className="text-sm text-[#8B93A8] leading-relaxed">
    Historical reliability assessment based on analysis of{' '}
    <span className="text-[#E8ECF4] font-medium">174 real BSEE/CSB incidents</span>{' '}
    with{' '}
    <span className="text-[#E8ECF4] font-medium">558 barrier observations</span>{' '}
    from Loss of Containment events in oil &amp; gas operations.
    Barrier failure patterns identified using XGBoost with SHAP explainability,
    validated through 5-fold cross-validation.
  </p>
</div>
```

**Do NOT delete ModelKPIs.tsx** — it still has value in the Drivers & HF tab or a future "Model Performance" section for technical reviewers. Just remove it from the Executive Summary where domain experts see it first.

**Why:** Fidel needs to know "this is based on real incident data" not "F1=0.928". The provenance builds trust; the metrics don't.

---

## Task 5: Investigate and Fix Empty Condition Column

**File:** `frontend/components/dashboard/RankedBarriers.tsx` (frontend) + check `src/api/main.py` or `src/modeling/predict.py` (backend)

**What to do:**
The "Condition" column in the Ranked Barriers table shows '—' for every row. The frontend code already reads `pred.barrier_condition_display ?? '—'` (line ~100 in RankedBarriers.tsx), so the issue is likely the **backend not returning this field** in the /predict response.

**Step 1:** Check the FastAPI `/predict` endpoint response. Look at `src/api/main.py` or `src/api/schemas.py` — is `barrier_condition_display` being populated in the response? Search for `barrier_condition_display` in the backend code.

**Step 2:** If the backend has Model 3 (multiclass barrier condition), wire it:
- Model 3 predicts: effective / degraded / ineffective
- Map to display strings using `configs/mappings/barrier_condition.yaml`
- Return as `barrier_condition_display` in the predict response

**Step 3:** If Model 3 is not loaded in the API (check `src/modeling/predict.py`), this becomes a backend task: load `model3_xgb.joblib`, predict, map the class label to a display name, include in response.

**If Model 3 is genuinely not available** in the current deployment, then change the column header from "Condition" to something that won't look broken. Either hide the column entirely or show the risk level text there instead:
```tsx
condition: pred.barrier_condition_display ?? PILL_LABELS[barrier.riskLevel] ?? '—',
```

**Why:** An empty column in every row signals "this feature doesn't work."

---

## Task 6: Add Explanatory Header to Apriori Rules Table

**File:** `frontend/components/dashboard/DriversHF.tsx`

**What to do:**
Find the `AprioriRulesTable` component. Add a description paragraph below the `<h3>` heading:

```tsx
<h3 className="text-base font-semibold mb-1 text-[#E8ECF4]">
  Co-failure Association Rules
</h3>
<p className="text-sm text-[#5A6178] mb-4">
  When the antecedent barrier family fails in an incident, the consequent barrier family
  also fails with the shown confidence. Based on Apriori analysis of 174 BSEE/CSB incident
  investigations.
</p>
```

**Why:** A table full of "Antecedent / Consequent / Confidence / Support / Lift / Count" with no explanation is opaque to anyone who isn't a data scientist.

---

## Verification Checklist

After completing all tasks, verify in browser:

- [ ] Dashboard has exactly 4 tabs: Executive Summary, Drivers & HF, Ranked Barriers, Evidence
- [ ] No "coming soon" placeholders anywhere
- [ ] PIF Prevalence chart x-axis goes 0% to 100% max
- [ ] All bar charts have value labels at end of bars
- [ ] Executive Summary shows "Assessment Basis" card instead of raw F1/MCC metrics
- [ ] Condition column in Ranked Barriers shows a value (or column is hidden if backend can't provide it)
- [ ] Apriori Rules table has an explanatory description
- [ ] No visual regressions — all existing functionality still works
- [ ] Run `cd frontend && npx vitest run` — all tests pass (update test expectations if tab count changed)

---

## Test Updates Required

The test file `__tests__/DashboardView.test.tsx` likely asserts on tab count or tab labels. Update it to reflect the new 4-tab structure. Search for any assertions on 'barrier-coverage', 'incident-trends', or 'risk-matrix' and remove them.

The test file `__tests__/ModelKPIs.test.tsx` should still pass since we're keeping the component — just not rendering it in the Executive Summary.
