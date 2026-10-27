import type { RiskKey } from '../api/types'

export type RGB = [number, number, number]

export const RISK_LEVELS: { key: RiskKey; label: string; color: RGB }[] = [
  { key: 'low', label: 'Low', color: [34, 160, 90] },
  { key: 'moderate', label: 'Moderate', color: [234, 196, 30] },
  { key: 'high', label: 'High', color: [240, 128, 30] },
  { key: 'severe', label: 'Severe', color: [214, 40, 40] },
  { key: 'no_travel', label: 'No Travel', color: [110, 30, 140] },
]

export const UNKNOWN_COLOR: RGB = [150, 160, 175]

export function riskColor(level: number | null | undefined): RGB {
  return level == null ? UNKNOWN_COLOR : RISK_LEVELS[level].color
}

export function rgbCss([r, g, b]: RGB, alpha = 1): string {
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** Continuous color on the 0–4 risk scale (interpolates between level colors). */
export function colorAt(t: number): RGB {
  const x = Math.min(Math.max(t, 0), 4)
  const lo = Math.floor(x)
  const hi = Math.min(lo + 1, 4)
  const f = x - lo
  const a = RISK_LEVELS[lo].color
  const b = RISK_LEVELS[hi].color
  return [0, 1, 2].map((i) => Math.round(a[i] + f * (b[i] - a[i]))) as RGB
}

export type HeatVariable = 'risk' | 'wind' | 'rain' | 'snow'

/**
 * Band edges mirror the backend thresholds (planner/domain/risk.py), so a
 * weather variable is colored by the risk band it alone would produce.
 */
export const HEAT_VARIABLES: Record<HeatVariable, { label: string; unit: string; edges: number[] | null }> = {
  risk: { label: 'Overall risk (with load)', unit: '', edges: null },
  wind: { label: 'Wind', unit: 'mph', edges: [25, 35, 45, 55] },
  rain: { label: 'Rain', unit: 'in/hr', edges: [0.1, 0.25, 0.5, 1.0] },
  snow: { label: 'Snow', unit: 'in/hr', edges: [0.5, 1, 2, 3] },
}

/** Map a raw value onto the continuous 0–4 risk scale using band edges. */
export function toRiskScale(value: number, edges: number[] | null): number {
  if (!edges) return value
  let lower = 0
  for (let i = 0; i < edges.length; i++) {
    if (value < edges[i]) return i + (value - lower) / (edges[i] - lower)
    lower = edges[i]
  }
  return 4
}
