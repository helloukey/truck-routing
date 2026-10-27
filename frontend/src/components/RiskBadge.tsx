import { RISK_LEVELS, riskColor, rgbCss } from '../lib/risk'

export function RiskBadge({ level }: { level: number | null | undefined }) {
  const label = level == null ? 'Unknown' : RISK_LEVELS[level].label
  const dark = level == null || level === 1 // yellow & gray need dark text
  return (
    <span className="risk-badge" style={{ background: rgbCss(riskColor(level)), color: dark ? '#1f2937' : '#fff' }}>
      {label}
    </span>
  )
}
