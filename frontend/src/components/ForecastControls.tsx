import { type Dispatch, type SetStateAction, useEffect, useState } from 'react'

import { formatTime } from '../lib/format'
import { HEAT_VARIABLES, type HeatVariable, RISK_LEVELS, colorAt, rgbCss } from '../lib/risk'

export const MAX_HOUR = 48
const PLAY_HOURS_PER_SECOND = 3
const SLIDER_STEP = 0.1 // fractional hours: the map cross-fades between hourly frames

interface Props {
  start: string | null // heatmap hour 0; null while loading
  hour: number
  onHour: Dispatch<SetStateAction<number>>
  variable: HeatVariable
  onVariable: (v: HeatVariable) => void
  loading: boolean
  error: string | null
}

function hourLabel(h: number): string {
  const whole = Math.floor(h)
  const minutes = Math.round((h - whole) * 60)
  return minutes ? `+${whole}h ${minutes.toString().padStart(2, '0')}m` : `+${whole}h`
}

export function ForecastControls({ start, hour, onHour, variable, onVariable, loading, error }: Props) {
  const [playing, setPlaying] = useState(false)

  // Continuous playback on animation frames (smooth at any refresh rate).
  useEffect(() => {
    if (!playing) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      const step = ((now - last) / 1000) * PLAY_HOURS_PER_SECOND
      last = now
      onHour((h) => (h + step >= MAX_HOUR ? 0 : h + step))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, onHour])

  const disabled = !start
  const at = start ? new Date(Date.parse(start) + hour * 3_600_000) : null
  const v = HEAT_VARIABLES[variable]

  return (
    <div className="forecast-panel">
      <div className="forecast-top">
        <button
          type="button"
          className="play"
          onClick={() => setPlaying((p) => !p)}
          disabled={disabled}
          aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <div className="forecast-time">
          <strong>{hourLabel(hour)}</strong>
          <span>{at ? formatTime(at) : loading ? 'Loading forecast…' : (error ?? 'Plan a trip to see the forecast')}</span>
        </div>
        <select value={variable} onChange={(e) => onVariable(e.target.value as HeatVariable)} aria-label="Heatmap layer">
          {(Object.keys(HEAT_VARIABLES) as HeatVariable[]).map((k) => (
            <option key={k} value={k}>
              {HEAT_VARIABLES[k].label}
            </option>
          ))}
        </select>
      </div>
      <input
        type="range"
        min={0}
        max={MAX_HOUR}
        step={SLIDER_STEP}
        value={hour}
        disabled={disabled}
        onChange={(e) => {
          setPlaying(false)
          onHour(Number(e.target.value))
        }}
        aria-label="Forecast hour"
        aria-valuetext={at ? `${hourLabel(hour)}, ${formatTime(at)}` : hourLabel(hour)}
      />
      <div className="legend" aria-label="Legend">
        {RISK_LEVELS.map((l, i) => (
          <span key={l.key}>
            <i style={{ background: rgbCss(colorAt(i)) }} />
            {v.edges ? (i === 0 ? `<${v.edges[0]}` : i === 4 ? `>${v.edges[3]}` : `${v.edges[i - 1]}–${v.edges[i]}`) : l.label}
          </span>
        ))}
        {v.unit && <span className="muted">{v.unit}</span>}
        <span className="legend-truck">
          <i className="truck-dot" /> Truck at this time
        </span>
      </div>
    </div>
  )
}
