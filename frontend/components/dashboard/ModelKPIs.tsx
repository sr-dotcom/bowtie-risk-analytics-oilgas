'use client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface KpiCard {
  label: string
  value: string
  subtitle: string
  category: 'model1' | 'model2'
}

// ---------------------------------------------------------------------------
// Data constants (XGBoost 5-fold CV means from training_report.json)
// ---------------------------------------------------------------------------

const KPI_DATA = {
  model1_f1:  { value: 0.928, std: 0.019 },
  model1_mcc: { value: 0.793, std: 0.037 },
  model2_f1:  { value: 0.348, std: 0.060 },
  model2_mcc: { value: 0.266, std: 0.075 },
}

// ---------------------------------------------------------------------------
// Pure function
// ---------------------------------------------------------------------------

/**
 * Build the 4 model KPI cards from frozen training constants.
 * Returns exactly 4 KpiCard items in display order:
 *   [0] Barrier Failure F1   (model1)
 *   [1] Barrier Failure MCC  (model1)
 *   [2] Human Factor F1      (model2)
 *   [3] Human Factor MCC     (model2)
 */
export function buildKpiCards(): KpiCard[] {
  return [
    {
      label: 'Barrier Failure F1',
      value: KPI_DATA.model1_f1.value.toFixed(3),
      subtitle: `±${KPI_DATA.model1_f1.std} (5-fold CV)`,
      category: 'model1',
    },
    {
      label: 'Barrier Failure MCC',
      value: KPI_DATA.model1_mcc.value.toFixed(3),
      subtitle: `±${KPI_DATA.model1_mcc.std} (5-fold CV)`,
      category: 'model1',
    },
    {
      label: 'Human Factor F1',
      value: KPI_DATA.model2_f1.value.toFixed(3),
      subtitle: `±${KPI_DATA.model2_f1.std} (5-fold CV)`,
      category: 'model2',
    },
    {
      label: 'Human Factor MCC',
      value: KPI_DATA.model2_mcc.value.toFixed(3),
      subtitle: `±${KPI_DATA.model2_mcc.std} (5-fold CV)`,
      category: 'model2',
    },
  ]
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ModelKPIs() {
  const cards = buildKpiCards()

  return (
    <div data-testid="model-kpis" className="grid grid-cols-2 gap-3">
      {cards.map((card) => (
        <div
          key={card.label}
          className={[
            'bg-[#242836] rounded-lg p-3',
            'border-l-4',
            card.category === 'model1' ? 'border-blue-500' : 'border-purple-500',
          ].join(' ')}
        >
          <p className="text-xs text-[#5A6178] mb-1">{card.label}</p>
          <p className="text-2xl font-bold text-[#E8ECF4]">{card.value}</p>
          <p className="text-xs text-[#5A6178] mt-1">{card.subtitle}</p>
        </div>
      ))}
    </div>
  )
}
