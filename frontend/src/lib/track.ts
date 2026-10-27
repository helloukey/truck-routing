import type { GeometryPoint, Route } from '../api/types'

export type LonLat = [number, number]

/** Position along a route after `elapsed` seconds of driving (clamped to the ends). */
export function positionAt(geometry: GeometryPoint[], elapsed: number): LonLat {
  const first = geometry[0]
  const last = geometry[geometry.length - 1]
  if (elapsed <= first[2]) return [first[0], first[1]]
  if (elapsed >= last[2]) return [last[0], last[1]]

  let lo = 0
  let hi = geometry.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (geometry[mid][2] <= elapsed) lo = mid
    else hi = mid
  }
  const a = geometry[lo]
  const b = geometry[hi]
  const f = b[2] === a[2] ? 0 : (elapsed - a[2]) / (b[2] - a[2])
  return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])]
}

export function departureMs(route: Route): number {
  return Date.parse(route.checkpoints[0].eta)
}

export interface RiskSegment {
  path: LonLat[]
  level: number | null
}

/**
 * Split a route into the stretches between consecutive checkpoints. Each stretch
 * takes the worse of its two endpoint risks — the same rule the backend uses
 * to count risk miles, so the map and the summary agree.
 */
export function riskSegments(route: Route): RiskSegment[] {
  const t0 = departureMs(route)
  const cps = route.checkpoints
  const geo = route.geometry
  const segments: RiskSegment[] = []
  let v = 0

  for (let i = 0; i < cps.length - 1; i++) {
    const start = (Date.parse(cps[i].eta) - t0) / 1000
    const end = (Date.parse(cps[i + 1].eta) - t0) / 1000
    const path: LonLat[] = [positionAt(geo, start)]
    while (v < geo.length && geo[v][2] <= start) v++
    while (v < geo.length && geo[v][2] < end) {
      path.push([geo[v][0], geo[v][1]])
      v++
    }
    path.push(positionAt(geo, end))

    const levels = [cps[i].risk?.level, cps[i + 1].risk?.level].filter((l): l is NonNullable<typeof l> => l != null)
    segments.push({ path, level: levels.length ? Math.max(...levels) : null })
  }
  return segments
}
