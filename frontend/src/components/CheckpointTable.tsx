import type { Route } from '../api/types'
import { LOCAL_ZONE, formatClock } from '../lib/format'
import type { CheckpointRef } from '../map/MapView'
import { RiskBadge } from './RiskBadge'

interface Props {
  route: Route
  title: string
  onHover: (ref: CheckpointRef | null) => void
}

export function CheckpointTable({ route, title, onHover }: Props) {
  return (
    <section className="checkpoints">
      <h3>
        {title} checkpoints <span className="muted">({route.checkpoints.length})</span>
      </h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA ({LOCAL_ZONE})</th>
              <th title="Sustained wind (gust)">Wind mph</th>
              <th>Rain in/hr</th>
              <th>Snow in/hr</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody onMouseLeave={() => onHover(null)}>
            {route.checkpoints.map((c, i) => (
              <tr
                key={i}
                onMouseEnter={() => onHover({ routeId: route.id, index: i })}
                title={c.risk?.reasons.join('\n') || undefined}
              >
                <td>{c.mile.toFixed(0)}</td>
                <td>{formatClock(c.eta)}</td>
                {c.weather ? (
                  <>
                    <td>
                      {c.weather.wind_mph.toFixed(0)} <span className="muted">({c.weather.gust_mph.toFixed(0)})</span>
                    </td>
                    <td>{c.weather.rain_in_hr.toFixed(2)}</td>
                    <td>{c.weather.snow_in_hr.toFixed(2)}</td>
                  </>
                ) : (
                  <td colSpan={3} className="muted">
                    Beyond forecast
                  </td>
                )}
                <td>
                  <RiskBadge level={c.risk?.level} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
