// Copy of configs/denominators.json — Turbopack cannot resolve outside frontend/.
// Keep in sync with configs/denominators.json. M005 work: add auto-sync script.
import denominatorsData from './denominators.json'

interface Denominator {
  key: string
  value: number | string
  source_file: string
  source_query?: string
  scope_description: string
  regeneration_status: string
  regeneration_note: string
}

interface DenominatorsConfig {
  as_of_commit: string
  as_of_date: string
  note: string
  denominators: Denominator[]
}

const config = denominatorsData as DenominatorsConfig

export function getDenominator(key: string): Denominator {
  const found = config.denominators.find((d) => d.key === key)
  if (!found) throw new Error(`Denominator not found: ${key}`)
  return found
}

export function getDenominatorValue(key: string): number | string {
  return getDenominator(key).value
}
