# Sprint 3: Bowtie SVG Diagram Overhaul

**Goal:** The bowtie diagram becomes the hero of the product. Barriers sit ON pathway lines as gates, not floating boxes. The visual language matches BowTieXP's industry-standard representation. A process safety engineer sees this and immediately recognizes the bowtie methodology.

**Time estimate:** 4-6 hours  
**THIS IS THE HIGHEST-RISK SPRINT. Verify in browser after EVERY change. Do NOT batch multiple changes.**  
**Depends on:** Sprint 2 complete (drawer replaces sidebar, so diagram gets full width)

---

## Reference: BowTieXP Visual Language

Study the uploaded reference image `bowtiexp-reference.png`. Key visual elements:

1. **Pathway lines are continuous curves** from threat → through barriers → to top event (prevention side) and from top event → through barriers → to consequences (mitigation side)
2. **Barriers interrupt the pathway** — the line enters the barrier block on the left edge and exits on the right edge. The barrier is a GATE on the road, not a signpost beside it.
3. **Barriers are vertical white blocks** with stacked text: name (bold blue), role description (blue underlined), barrier type label + colored square
4. **Thin vertical color bar** on the LEFT edge of each barrier (effectiveness indicator — our risk level)
5. **Top event is a large orange/red circle** centered in the diagram
6. **Hazard sits above** in a yellow/black hazard-stripe box, connected to the top event
7. **Threats are left-aligned boxes** with blue borders, containing threat name and contribution label
8. **Consequences are right-aligned boxes** with red borders
9. **Background is light gray** (#E0E0E0) — this is already correct
10. **Pathway lines are gray** (#AAA, 2px) — already correct

---

## Task 1: Redesign Barrier Positioning — Barriers ON Pathways

**File:** `frontend/components/diagram/BowtieSVG.tsx` — the `computeLayout()` function

**Current problem:** Barriers are positioned at calculated (x, y) coordinates that place them NEAR the pathway lines but not precisely ON them. The pathway curves go from threat center to barrier center, but the barriers render as separate boxes that float near the curve.

**What to change:**

The key insight: barriers should be positioned such that the pathway line ENTERS the left edge of the barrier and EXITS the right edge. The barrier Y position should be computed as the point on the pathway where the line would naturally cross at that X coordinate.

**For prevention barriers on a given threat pathway:**
- Divide the horizontal space between the threat right edge and the top event left tangent into N+1 segments (where N = number of barriers)
- Each barrier's X is at the segment boundary
- Each barrier's Y is interpolated along the straight/curved line from threat center to top event center at that X position
- The pathway curve segments connect: threat-right-edge → barrier-left-edge, barrier-right-edge → next-barrier-left-edge, last-barrier-right-edge → top-event-tangent

**For mitigation barriers:**
- Same logic but from top event right tangent to each consequence
- Currently all mitigation barriers sit on the center line (CY). In BowTieXP, mitigation barriers fan out from the top event toward their respective consequences, similar to how prevention barriers converge from threats.

**Implementation approach for prevention barriers:**

```typescript
// For each threat, compute barrier positions along the pathway
for (const tp of tPos) {
  const bs = prevByThreat.get(tp.id) ?? []
  const n = bs.length
  
  // Start point: threat right edge center
  const startX = THREAT_X + THREAT_W
  const startY = tp.cy
  
  // End point: top event left tangent
  const endX = TOP_EVENT_CX - TOP_EVENT_R
  const endY = CY
  
  // Distribute barriers evenly in the horizontal space
  const totalHSpace = endX - startX
  const segmentWidth = totalHSpace / (n + 1)
  
  for (let j = 0; j < n; j++) {
    // Barrier center X is at segment (j+1)
    const bCenterX = startX + (j + 1) * segmentWidth
    const bx = bCenterX - BARRIER_W / 2
    
    // Interpolate Y along the straight line from start to end
    const t = (bCenterX - startX) / (endX - startX)
    const bCenterY = startY + t * (endY - startY)
    const by = bCenterY - BARRIER_H / 2
    
    bPos.push({ ...bs[j], x: bx, y: by, cy: bCenterY })
  }
}
```

**Pathway curves should connect edge-to-edge:**
```typescript
// Threat right edge → first barrier LEFT edge
paths.push({ d: sCurve(startX, startY, bs[0].x, bs[0].cy) })

// Between barriers: right edge → left edge  
for (let i = 0; i < bs.length - 1; i++) {
  paths.push({
    d: sCurve(bs[i].x + BARRIER_W, bs[i].cy, bs[i + 1].x, bs[i + 1].cy)
  })
}

// Last barrier RIGHT edge → top event tangent
paths.push({ d: sCurve(last.x + BARRIER_W, last.cy, endX, endY) })
```

This is the critical difference from the current code — pathways go to barrier EDGES, not centers.

**Verify:** After this change, check that pathway lines visually "enter" and "exit" each barrier block.

---

## Task 2: Barrier Block Visual — Color Stripe + Selected State

**File:** `frontend/components/diagram/BowtieSVG.tsx` — the barrier rendering section (LAYER 3)

**Current state:** The effectiveness indicator is a tiny 8x22px colored rectangle positioned 12px to the LEFT of the barrier. This is disconnected from the barrier block.

**What to change:**

Move the color stripe INSIDE the barrier block as a vertical bar on the left edge:

```tsx
{/* Barrier block */}
<g key={`b-${b.id}`} style={{ cursor: 'pointer' }} onClick={() => onBarrierClick(b.id)}>
  {/* Selection glow — behind everything */}
  {isSelected && (
    <rect
      x={b.x - 4}
      y={b.y - 4}
      width={BARRIER_W + 8}
      height={BARRIER_H + 8}
      fill="none"
      stroke="#3B82F6"
      strokeWidth={2.5}
      rx={3}
      opacity={0.6}
      filter="url(#glow)"
    />
  )}
  
  {/* White barrier body */}
  <rect
    x={b.x}
    y={b.y}
    width={BARRIER_W}
    height={BARRIER_H}
    fill="white"
    stroke={isSelected ? '#3B82F6' : '#999'}
    strokeWidth={isSelected ? 1.5 : 0.5}
  />
  
  {/* Risk level color stripe — left edge, INSIDE the barrier */}
  <rect
    x={b.x}
    y={b.y}
    width={6}
    height={BARRIER_H}
    fill={riskColor(b.risk_level)}
  />
  
  {/* Content: name, role, type — shifted right to accommodate stripe */}
  {nameLines.map((line, li) => (
    <text
      key={li}
      x={b.x + 14}
      y={b.y + 16 + li * 14}
      fill={BLUE}
      fontSize={12}
      fontWeight={700}
    >
      {line}
    </text>
  ))}
  
  {/* Role description */}
  {b.barrier_role && (
    <text
      x={b.x + 14}
      y={b.y + 28 + nameLines.length * 14}
      fill={BLUE}
      fontSize={10}
      textDecoration="underline"
    >
      {b.barrier_role.length > 24 ? b.barrier_role.slice(0, 24) + '…' : b.barrier_role}
    </text>
  )}
  
  {/* Type badge with colored square */}
  <rect
    x={b.x + 14}
    y={b.y + BARRIER_H - 20}
    width={8}
    height={8}
    fill={ti.color}
  />
  <text
    x={b.x + 26}
    y={b.y + BARRIER_H - 12}
    fill={DARK_BLUE}
    fontSize={10}
  >
    {ti.label}
  </text>
</g>
```

**Add a glow filter** in the `<defs>` section for the selection state:
```tsx
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
  <feGaussianBlur stdDeviation="3" result="coloredBlur" />
  <feMerge>
    <feMergeNode in="coloredBlur" />
    <feMergeNode in="SourceGraphic" />
  </feMerge>
</filter>
```

**Remove** the separate LAYER 2 (Effectiveness indicators) section — the colored stripe is now integrated into the barrier block.

**Verify:** Barriers should have a thin colored stripe on the left edge (green/amber/red), and clicking a barrier should show a subtle blue glow outline.

---

## Task 3: Translate System Codes to Domain Language

**File:** `frontend/components/diagram/BowtieSVG.tsx` — the `typeInfo()` function

**Current state:**
```typescript
case 'engineering': return { color: '#3B82F6', label: 'A-HW Active hardware' }
case 'administrative': return { color: '#8B5CF6', label: 'ST Socio technical' }
```

These labels ('A-HW Active hardware', 'ST Socio technical', 'BEH Behavioural') are internal taxonomy codes. Fidel's domain uses:

**What to change:**

```typescript
function typeInfo(t: string): { color: string; label: string } {
  switch (t) {
    case 'engineering':
      return { color: '#3B82F6', label: 'Engineered Safety Barrier' }
    case 'administrative':
      return { color: '#8B5CF6', label: 'Administrative Control' }
    case 'ppe':
      return { color: '#EC4899', label: 'Behavioural Barrier' }
    case 'active_human':
      return { color: '#14B8A6', label: 'Active Human Barrier' }
    case 'active_hw_human':
      return { color: '#6366F1', label: 'Active HW + Human' }
    default:
      return { color: '#94A3B8', label: t.replace(/_/g, ' ') }
  }
}
```

**Also update** the contribution labels in `contribInfo()`. The current "HC High contribution" abbreviation is internal. Change to:
```typescript
function contribInfo(c: 'high' | 'medium' | 'low') {
  switch (c) {
    case 'high':   return { color: '#DC2626', label: 'High Contribution' }
    case 'medium': return { color: '#F59E0B', label: 'Medium Contribution' }
    case 'low':    return { color: '#F59E0B', label: 'Low Contribution' }
  }
}
```

**Apply the same translations** in any other component that shows barrier_type or contribution level. Search the codebase for 'A-HW', 'ST Socio', 'BEH Behaviour' to find all instances.

**Verify:** The diagram should show "Engineered Safety Barrier" not "A-HW Active hardware" on every barrier block.

---

## Task 4: Improve Mitigation Side Layout

**File:** `frontend/components/diagram/BowtieSVG.tsx` — mitigation barrier positioning

**Current problem:** All mitigation barriers sit on the horizontal center line (CY) regardless of which consequence they protect. In BowTieXP, mitigation barriers fan out from the top event toward their respective consequences, just like prevention barriers fan in from threats.

**What to change:**

Apply the same distribution logic to mitigation barriers. Since mitigation barriers don't currently have a `consequenceId`, distribute them evenly across all consequence pathways:

```typescript
// Mitigation: distribute barriers across consequences
if (mit.length > 0 && cPos.length > 0) {
  // If there are more barriers than consequences, assign round-robin
  for (let j = 0; j < mit.length; j++) {
    const targetConsequence = cPos[j % cPos.length]
    
    // Number of barriers assigned to this consequence
    const barriersForThisConsequence = mit.filter((_, k) => k % cPos.length === j % cPos.length)
    const indexInGroup = barriersForThisConsequence.indexOf(mit[j])
    const groupSize = barriersForThisConsequence.length
    
    const startX = TOP_EVENT_CX + TOP_EVENT_R
    const endX = CONSEQUENCE_X
    const totalHSpace = endX - startX
    const segmentWidth = totalHSpace / (groupSize + 1)
    
    const bCenterX = startX + (indexInGroup + 1) * segmentWidth
    const bx = bCenterX - BARRIER_W / 2
    
    const t = (bCenterX - startX) / (endX - startX)
    const bCenterY = CY + t * (targetConsequence.cy - CY)
    const by = bCenterY - BARRIER_H / 2
    
    bPos.push({ ...mit[j], x: bx, y: by, cy: bCenterY })
  }
}
```

This mirrors the prevention side logic: barriers are positioned along the line from top event to their target consequence.

**Note:** This is a simplification. If it looks wrong with the current barrier/consequence count, fall back to the simpler approach of centering mitigation barriers but at staggered Y positions.

**Verify:** Mitigation barriers should fan out from the top event toward consequences, not all sit on one horizontal line.

---

## Task 5: Increase Canvas and Readability

**File:** `frontend/components/diagram/BowtieSVG.tsx` — constants and viewBox

**What to change:**

1. **Increase viewBox width** from 1400 to 1600 to give more breathing room between elements:
```typescript
const CONSEQUENCE_X = 1300  // was 1150
// viewBox: "0 0 1600 ${H}"
```

2. **Increase barrier height** slightly to fit 3 rows of text (name + role + type):
```typescript
const BARRIER_H = 90  // was 78
```

3. **Add subtle drop shadow** to barrier blocks to lift them off the canvas:
```tsx
<filter id="barrier-shadow" x="-5%" y="-5%" width="110%" height="110%">
  <feDropShadow dx="1" dy="1" stdDeviation="2" floodOpacity="0.15" />
</filter>
```
Apply: `filter="url(#barrier-shadow)"` on barrier `<rect>`.

4. **Add pan support** — the current zoom buttons are tiny. Add mouse wheel zoom and click-drag pan, OR at minimum make the zoom controls more prominent.

**Verify:** All text should be readable without zooming. No text should overflow barrier boxes.

---

## Task 6: Threat and Consequence Box Borders

**File:** `frontend/components/diagram/BowtieSVG.tsx` — threat and consequence rendering

**What to change:**

Match BowTieXP visual language:
- **Threat boxes:** thick blue border (3px, `#0000EE`), white fill
- **Consequence boxes:** thick red border (3px, `#DC2626`), white fill

Find the threat rendering section and update:
```tsx
<rect
  x={tp.x} y={tp.y}
  width={THREAT_W} height={THREAT_H}
  fill="white"
  stroke={BLUE}
  strokeWidth={3}  // was likely 1 or 2
/>
```

Consequence:
```tsx
<rect
  x={cp.x} y={cp.y}
  width={CONSEQUENCE_W} height={CONSEQUENCE_H}
  fill="white"
  stroke="#DC2626"
  strokeWidth={3}
/>
```

**Verify:** Threats have clearly visible blue borders, consequences have clearly visible red borders. The differentiation between prevention side (blue) and mitigation side (red) should be immediately obvious.

---

## Verification Checklist

After completing all tasks, verify in browser:

- [ ] Pathway lines visually enter barriers on the left edge and exit on the right edge
- [ ] Barriers look like "gates on a road" not "floating signposts"
- [ ] Each barrier has a colored stripe on its left edge (green/amber/red)
- [ ] Clicking a barrier shows a blue glow selection state on the diagram
- [ ] All barrier type labels show domain language ("Engineered Safety Barrier" not "A-HW Active hardware")
- [ ] Contribution labels show full words ("High Contribution" not "HC High contribution")
- [ ] Mitigation barriers fan out toward consequences (not all on one line)
- [ ] Threat boxes have thick blue borders
- [ ] Consequence boxes have thick red borders
- [ ] Top event is a prominent orange/red circle
- [ ] Hazard stripe box sits above the top event
- [ ] All text is readable without zooming
- [ ] Clicking a barrier opens the detail drawer (Sprint 2)
- [ ] Run tests: `cd frontend && npx vitest run`

---

## HIGH RISK WARNING

This sprint modifies the core SVG rendering. Do NOT attempt multiple tasks at once. The flow should be:

1. Make ONE change (e.g., barrier positioning)
2. Save
3. Check browser
4. If it looks wrong, fix it before moving to the next task
5. If it looks right, commit and move on

The BowtieSVG component is 697 lines of coordinate math. One wrong constant breaks the entire layout. Work incrementally.
