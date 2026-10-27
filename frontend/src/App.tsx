import { useCallback, useState } from 'react'

import type { Plan } from './api/types'
import { CheckpointTable } from './components/CheckpointTable'
import { ForecastControls } from './components/ForecastControls'
import { Recommendation, RouteList } from './components/RouteList'
import { TripForm } from './components/TripForm'
import { useTripPlanner } from './hooks/useTripPlanner'
import { routeName } from './lib/format'
import type { HeatVariable } from './lib/risk'
import { type CheckpointRef, MapView } from './map/MapView'

export default function App() {
  const { plan, planLoading, planError, heatmap, heatLoading, heatError, submit } = useTripPlanner()
  const [choice, setChoice] = useState<{ plan: Plan; routeId: string } | null>(null)
  const [highlighted, setHighlighted] = useState<CheckpointRef | null>(null)
  const [hour, setHour] = useState(0)
  const [heatVariable, setHeatVariable] = useState<HeatVariable>('risk')

  // A user's pick only applies to the plan it was made on; new plans start on the recommendation.
  const selectedId = plan && choice?.plan === plan ? choice.routeId : (plan?.recommended_route_id ?? null)
  const setSelectedId = useCallback((routeId: string) => plan && setChoice({ plan, routeId }), [plan])

  const selectedRoute = plan?.routes.find((r) => r.id === selectedId) ?? null

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="app-header">
          <h1>Weather-Aware Truck Routing</h1>
          <p>Compare truck routes by forecast weather risk at your ETA along each route.</p>
        </header>

        <TripForm loading={planLoading} onSubmit={submit} />
        {planError && (
          <div className="error-box" role="alert">
            {planError}
          </div>
        )}

        {plan && (
          <>
            <Recommendation plan={plan} />
            <RouteList plan={plan} selectedId={selectedId} onSelect={setSelectedId} />
          </>
        )}
        {selectedRoute && (
          <CheckpointTable route={selectedRoute} title={routeName(selectedRoute.id)} onHover={setHighlighted} />
        )}
      </aside>

      <main className="map-pane">
        <MapView
          plan={plan}
          heatmap={heatmap}
          heatVariable={heatVariable}
          hour={hour}
          selectedId={selectedId}
          onSelect={setSelectedId}
          highlighted={highlighted}
        />
        {planLoading && <div className="map-status">Planning routes and sampling weather…</div>}
        <ForecastControls
          start={heatmap?.start ?? null}
          hour={hour}
          onHour={setHour}
          variable={heatVariable}
          onVariable={setHeatVariable}
          loading={heatLoading}
          error={heatError}
        />
      </main>
    </div>
  )
}
