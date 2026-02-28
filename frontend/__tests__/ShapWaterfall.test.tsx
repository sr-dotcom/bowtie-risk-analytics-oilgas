import { describe, it, expect } from 'vitest'
// Export buildWaterfallData from ShapWaterfall for testing
import { buildWaterfallData } from '@/components/panel/ShapWaterfall'

describe('buildWaterfallData', () => {
  it('computes correct offsets for positive values', () => {
    const shap = [
      { feature: 'a', value: 0.1, category: 'barrier' as const },
      { feature: 'b', value: 0.2, category: 'barrier' as const },
    ]
    const data = buildWaterfallData(shap, 0.5)
    // Sorted by |value| desc: b(0.2) then a(0.1)
    expect(data[0].feature).toBe('b')
    expect(data[0].offset).toBeCloseTo(0.5) // starts at base
    expect(data[0].value).toBeCloseTo(0.2)
    expect(data[1].feature).toBe('a')
    expect(data[1].offset).toBeCloseTo(0.7) // 0.5 + 0.2
    expect(data[1].value).toBeCloseTo(0.1)
  })

  it('handles negative SHAP values with correct offset', () => {
    const shap = [
      { feature: 'pos', value: 0.3, category: 'barrier' as const },
      { feature: 'neg', value: -0.2, category: 'barrier' as const },
    ]
    const data = buildWaterfallData(shap, 0.5)
    // pos first (|0.3| > |-0.2|)
    expect(data[0].offset).toBeCloseTo(0.5)
    expect(data[0].value).toBeCloseTo(0.3)
    // neg: running is 0.8 (0.5+0.3), negative offset = 0.8 + (-0.2) = 0.6
    expect(data[1].offset).toBeCloseTo(0.6)
    expect(data[1].value).toBeCloseTo(0.2) // absolute value for bar width
    expect(data[1].raw).toBeCloseTo(-0.2) // raw value preserves sign
  })

  it('limits to top 10 features', () => {
    const shap = Array.from({ length: 15 }, (_, i) => ({
      feature: `f${i}`,
      value: 0.01 * (i + 1),
      category: 'barrier' as const,
    }))
    const data = buildWaterfallData(shap, 0.5)
    expect(data.length).toBe(10)
  })

  it('returns empty array for empty input', () => {
    expect(buildWaterfallData([], 0.5)).toEqual([])
  })
})
