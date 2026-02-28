import { describe, it, expect } from 'vitest'
import { mapProbabilityToRiskLevel } from '@/lib/riskScore'

const thresholds = { p80: 0.72, p60: 0.45 }

describe('mapProbabilityToRiskLevel', () => {
  it('returns red for probability above p80', () => {
    expect(mapProbabilityToRiskLevel(0.99, thresholds)).toBe('red')
  })
  it('returns red at exactly p80 boundary (>=)', () => {
    expect(mapProbabilityToRiskLevel(0.72, thresholds)).toBe('red')
  })
  it('returns amber for probability between p60 and p80', () => {
    expect(mapProbabilityToRiskLevel(0.60, thresholds)).toBe('amber')
  })
  it('returns amber at exactly p60 boundary (>=)', () => {
    expect(mapProbabilityToRiskLevel(0.45, thresholds)).toBe('amber')
  })
  it('returns green for probability below p60', () => {
    expect(mapProbabilityToRiskLevel(0.30, thresholds)).toBe('green')
  })
  it('returns green for zero probability', () => {
    expect(mapProbabilityToRiskLevel(0.0, thresholds)).toBe('green')
  })
})
