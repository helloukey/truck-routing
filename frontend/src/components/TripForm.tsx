import { useState } from 'react'

import type { Place, PlanRequest } from '../api/types'
import { nextHourLocalInput } from '../lib/format'
import { LocationInput } from './LocationInput'

const INTERVALS = [10, 25, 50] as const
const EXAMPLE: { origin: Place; destination: Place } = {
  origin: { label: 'Chicago, IL, United States', lat: 41.8781, lon: -87.6298 },
  destination: { label: 'Denver, CO, United States', lat: 39.7392, lon: -104.9903 },
}

interface Props {
  loading: boolean
  onSubmit: (req: PlanRequest) => void
}

export function TripForm({ loading, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(nextHourLocalInput)
  const [load, setLoad] = useState('40000')
  const [intervalMi, setIntervalMi] = useState<(typeof INTERVALS)[number]>(25)

  const loadLb = Number(load)
  const canSubmit = origin && destination && departure && Number.isFinite(loadLb) && loadLb >= 0 && !loading

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit({
      origin,
      destination,
      // datetime-local is the browser's local time; send an absolute instant.
      departure: new Date(departure).toISOString(),
      load_lb: loadLb,
      interval_mi: intervalMi,
    })
  }

  return (
    <form className="trip-form" onSubmit={submit}>
      <LocationInput label="Origin" value={origin} onChange={setOrigin} placeholder="City or address" />
      <LocationInput label="Destination" value={destination} onChange={setDestination} placeholder="City or address" />

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            onChange={(e) => setDeparture(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={0}
            max={120000}
            step={500}
            value={load}
            onChange={(e) => setLoad(e.target.value)}
            required
          />
        </div>
      </div>

      <fieldset className="field">
        <legend>Weather checkpoint every</legend>
        <div className="segmented">
          {INTERVALS.map((mi) => (
            <label key={mi} className={intervalMi === mi ? 'on' : undefined}>
              <input type="radio" name="interval" value={mi} checked={intervalMi === mi} onChange={() => setIntervalMi(mi)} />
              {mi} mi
            </label>
          ))}
        </div>
      </fieldset>

      <div className="form-actions">
        <button type="submit" className="primary" disabled={!canSubmit}>
          {loading ? 'Planning…' : 'Find safest route'}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setOrigin(EXAMPLE.origin)
            setDestination(EXAMPLE.destination)
          }}
        >
          Try Chicago → Denver
        </button>
      </div>
    </form>
  )
}
