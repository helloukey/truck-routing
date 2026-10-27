import type { Plan } from '../api/types'
import { formatDuration, formatMiles, formatTime, routeName } from '../lib/format'
import { RiskBadge } from './RiskBadge'
import { RiskBar } from './RiskBar'

interface Props {
  plan: Plan
  selectedId: string | null
  onSelect: (id: string) => void
}

export function Recommendation({ plan }: { plan: Plan }) {
  const warning = plan.reasons[0]?.startsWith('Warning')
  return (
    <section className={`recommendation${warning ? ' warn' : ''}`} aria-live="polite">
      <h2>Recommended: {routeName(plan.recommended_route_id)}</h2>
      <ul>
        {plan.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </section>
  )
}

export function RouteList({ plan, selectedId, onSelect }: Props) {
  return (
    <section className="route-list" aria-label="Route options">
      {plan.routes.map((r) => {
        const m = r.summary.miles_by_risk
        const recommended = r.id === plan.recommended_route_id
        return (
          <button
            key={r.id}
            type="button"
            className={`route-card${r.id === selectedId ? ' selected' : ''}`}
            onClick={() => onSelect(r.id)}
            aria-pressed={r.id === selectedId}
          >
            <div className="route-card-head">
              <strong>{routeName(r.id)}</strong>
              {recommended && <span className="tag">★ Recommended</span>}
              <span className="spacer" />
              <RiskBadge level={r.summary.worst.level} />
            </div>
            <div className="route-stats">
              <span>{formatMiles(r.distance_mi)}</span>
              <span>{formatDuration(r.duration_s)}</span>
              <span>Arrive {formatTime(r.arrival)}</span>
            </div>
            <RiskBar milesByRisk={m} unknownMiles={r.summary.unknown_miles} />
            <div className="route-risk-miles">
              <span>Severe {m.severe.toFixed(0)} mi</span>
              <span>High {m.high.toFixed(0)} mi</span>
              <span>Avg risk {r.summary.avg_risk.toFixed(2)}</span>
              {m.no_travel > 0 && <span className="error-text">No Travel {m.no_travel.toFixed(0)} mi</span>}
              {r.summary.unknown_miles > 0 && <span>No forecast {r.summary.unknown_miles.toFixed(0)} mi</span>}
            </div>
          </button>
        )
      })}
    </section>
  )
}
