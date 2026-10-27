// Mirrors the Django API responses (backend/planner/api/serializers.py).

export type RiskLevel = 0 | 1 | 2 | 3 | 4
export type RiskKey = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel'

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string // ISO 8601 with offset
  load_lb: number
  interval_mi: 10 | 25 | 50
}

export interface CheckpointWeather {
  wind_mph: number
  gust_mph: number
  rain_in_hr: number
  snow_in_hr: number
}

export interface Checkpoint {
  lat: number
  lon: number
  mile: number
  eta: string
  weather: CheckpointWeather | null // null => beyond forecast horizon
  risk: { level: RiskLevel; label: string; reasons: string[] } | null
}

/** [lon, lat, elapsed seconds since departure] */
export type GeometryPoint = [number, number, number]

export interface Route {
  id: string
  distance_mi: number
  duration_s: number
  arrival: string
  geometry: GeometryPoint[]
  summary: {
    miles_by_risk: Record<RiskKey, number>
    unknown_miles: number
    avg_risk: number
    worst: { level: RiskLevel; label: string }
  }
  checkpoints: Checkpoint[]
}

export interface Plan {
  recommended_route_id: string
  reasons: string[]
  bounds: [number, number, number, number] // west, south, east, north
  routes: Route[]
}

export interface HeatmapGrid {
  west: number // center of column 0
  north: number // center of row 0
  dlon: number
  dlat: number
  cols: number
  rows: number
  cells: number[] // row-major indices inside the corridor
}

/** values[hour][i] belongs to grid.cells[i]; null => no forecast */
export type HourlyValues = (number | null)[][]

export interface Heatmap {
  start: string
  hours: number
  grid: HeatmapGrid
  risk: HourlyValues
  wind: HourlyValues
  rain: HourlyValues
  snow: HourlyValues
}
