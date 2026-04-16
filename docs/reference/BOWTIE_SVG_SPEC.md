# BowtieSVG.tsx — Convert Reference HTML to React Component

## WHAT THIS IS
Convert the layout algorithm from `frontend/public/bowtie-reference-v4.html` into 
`frontend/components/diagram/BowtieSVG.tsx` as a pure SVG React component.

The reference HTML is the SINGLE SOURCE OF TRUTH for all coordinate math, 
element sizing, pathway curves, fan angles, and visual styling. Do NOT 
improvise any layout values — extract them exactly from the reference.

## PROPS INTERFACE (already exists — preserve it)

```tsx
interface BowtieSVGProps {
  topEvent: string;
  threats: Array<{
    id: string;
    name: string;
    contribution: 'high' | 'medium' | 'low';
  }>;
  consequences: Array<{
    id: string;
    name: string;
  }>;
  barriers: Array<{
    id: string;
    name: string;
    side: 'prevention' | 'mitigation';
    barrier_type: string;
    barrier_role?: string;
    line_of_defense?: string;
    risk_level?: 'Low' | 'Medium' | 'High' | null;
    threatId?: string;
    consequenceId?: string;
  }>;
  selectedBarrierId: string | null;
  onBarrierClick: (barrierId: string) => void;
}
```

## CONVERSION RULES

### 1. Layout Constants (extract from reference v4)
```
CW = 1800
threatBoxW = 150, threatBoxH = 70
barrierBoxW = 130, barrierBoxH = 75
consBoxW = 150, consBoxH = 70
topEventR = 80
padding = 60
rowH = 160
barrierTabOverhang = 11
stemGap = 30
hazardW = 180, hazardH = 55
```

### 2. Dynamic Layout (runs on every render from props)
- `numRows = max(threats.length, consequences.length)`
- `contentH = (numRows + 1) * rowH`
- Vertical positions, fan angles, barrier zones — all computed exactly as in the reference
- viewBox height (CH) computed from bounding box of all elements + padding
- Group barriers by `threatId` (prevention) or `consequenceId` (mitigation)
- If a barrier has no threatId/consequenceId, distribute evenly

### 3. Fan Angles (CRITICAL — do not change)
```
leftFanAngles = [50, 0, -50]   // top threat → top of circle
rightFanAngles = [-50, 0, 50]  // top consequence → top of circle
```
For N threats/consequences, generate angles by interpolating from +50 to -50 (left) 
or -50 to +50 (right) with N evenly spaced values.

### 4. Pathway Lines
- Prevention: horizontal through barriers → Bezier curve to circle perimeter
- Mitigation: Bezier from circle perimeter → horizontal through barriers to consequence
- Bezier control points use the asymmetric formula from v4:
  - Prevention: cpX1 at 50%, cpX2 at 85% of span
  - Mitigation: cpX1 at 15%, cpX2 at 50% of span

### 5. Risk Level Indicators
- Consequence boxes get a white pill badge at bottom-right corner
- Color from `riskLevel`: High=#F44336, Medium=#FF9800, Low=#4CAF50
- Letter: H, M, or L
- If no risk_level on any consequence's linked barriers, don't show badge

### 6. Selected State
- When `selectedBarrierId` matches a barrier, highlight it:
  - Stroke: #2979FF (blue), strokeWidth: 3
  - Add subtle glow: filter with feDropShadow or just thicker stroke
- All other barriers keep default stroke (#333, 1.5px)

### 7. Click Handlers
- Each barrier `<g>` gets `onClick={() => onBarrierClick(barrier.id)}`
- Add `cursor: pointer` style
- Threat and consequence boxes are NOT clickable (for now)

### 8. Gradients and Patterns
Keep ALL gradient/pattern defs from the reference:
- topEventGrad (orange radial)
- threatGrad (blue radial)  
- consequenceGrad (red radial)
- hazardStripe (yellow-black diagonal)

### 9. Text Wrapping
- Barrier names may be long. Split on spaces, max 3 lines, truncate with "..." if needed
- Threat/consequence names: split on spaces, max 2 lines
- Top event text: split on spaces, max 3 lines
- Font sizes: barriers 12px, threats/consequences 13px, top event 13px, hazard 12px

### 10. The Hazard Box
- Text comes from a hardcoded or context-provided `hazard` string
- If not provided, use "High-pressure gas" as default
- Position: just above the top event circle, 30px stem

## INTEGRATION

In `BowtieApp.tsx`:
- When diagram view is active, render `<BowtieSVG {...props} />`
- Props come from BowtieContext
- `onBarrierClick` wires to `setSelectedBarrier`
- Wrap in a container div with `overflow: auto` for scroll/zoom
- Do NOT delete BowtieFlow.tsx (React Flow fallback)

## DO NOT
- Do NOT change any layout constants from the reference
- Do NOT use React Flow, D3, or any layout library — pure SVG math
- Do NOT add animation or transitions (performance on 20+ barriers)
- Do NOT run `next build` during an active dev server
- Do NOT modify the detail panel, Pathway View, or Analytics mode

## VERIFY
After implementation:
1. `cd frontend && npx tsc --noEmit` — zero type errors
2. `cd frontend && npx vitest run` — all tests pass
3. Visual check: diagram should match bowtie-reference-v4.html exactly
   when rendered with the same 3-threat, 3-consequence, 7-barrier test data
