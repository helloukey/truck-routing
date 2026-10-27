import type { RiskKey } from '../api/types'
import { RISK_LEVELS, UNKNOWN_COLOR, rgbCss } from '../lib/risk'

interface Props {
  milesByRisk: Record<RiskKey, number>
  unknownMiles: number
}

/** Stacked bar of miles spent in each risk level. */
export function RiskBar({ milesByRisk, unknownMiles }: Props) {
  const total = RISK_LEVELS.reduce((sum, l) => sum + milesByRisk[l.key], unknownMiles) || 1
  const parts = [
    ...RISK_LEVELS.map((l) => ({ label: l.label, miles: milesByRisk[l.key], color: l.color })),
    { label: 'No forecast', miles: unknownMiles, color: UNKNOWN_COLOR },
  ].filter((p) => p.miles > 0)

  return (
    <div
      className="risk-bar"
      role="img"
      aria-label={parts.map((p) => `${p.label} ${p.miles.toFixed(0)} miles`).join(', ')}
    >
      {parts.map((p) => (
        <span
          key={p.label}
          style={{ width: `${(p.miles / total) * 100}%`, background: rgbCss(p.color) }}
          title={`${p.label}: ${p.miles.toFixed(1)} mi`}
        />
      ))}
    </div>
  )
}
