import type { HeatmapGrid } from '../api/types'
import { colorAt, toRiskScale } from '../lib/risk'

/**
 * Renders one forecast hour as a smooth raster.
 *
 * Each grid cell becomes one pixel of a tiny canvas; upscaling it with canvas
 * bilinear smoothing gives a continuous heatmap whose pixel centers sit exactly
 * on the forecast points, at any zoom level. Cells outside the corridor (or
 * beyond the forecast) are transparent; canvas 2D blends premultiplied alpha, so
 * edges fade out cleanly instead of bleeding dark fringes.
 */

const UPSCALE = 12

/** Image bounds [west, south, east, north] — cell edges, half a step beyond the centers. */
export function heatBounds(g: HeatmapGrid): [number, number, number, number] {
  const east = g.west + (g.cols - 1) * g.dlon
  const south = g.north - (g.rows - 1) * g.dlat
  return [g.west - g.dlon / 2, south - g.dlat / 2, east + g.dlon / 2, g.north + g.dlat / 2]
}

/** Calm areas stay faint so the basemap reads through; risk gets more opaque. */
function alphaFor(t: number): number {
  const a = t < 1 ? 0.12 + 0.23 * t : Math.min(0.35 + 0.15 * (t - 1), 0.8)
  return Math.round(a * 255)
}

export function renderHeatFrame(
  grid: HeatmapGrid,
  values: (number | null)[],
  edges: number[] | null,
): HTMLCanvasElement {
  const small = document.createElement('canvas')
  small.width = grid.cols
  small.height = grid.rows
  const sctx = small.getContext('2d')!
  const img = sctx.createImageData(grid.cols, grid.rows)

  grid.cells.forEach((cell, i) => {
    const v = values[i]
    if (v == null) return
    const t = toRiskScale(v, edges)
    const [r, g, b] = colorAt(t)
    const o = cell * 4
    img.data[o] = r
    img.data[o + 1] = g
    img.data[o + 2] = b
    img.data[o + 3] = alphaFor(t)
  })
  sctx.putImageData(img, 0, 0)

  const big = document.createElement('canvas')
  big.width = grid.cols * UPSCALE
  big.height = grid.rows * UPSCALE
  const bctx = big.getContext('2d')!
  bctx.imageSmoothingEnabled = true
  bctx.imageSmoothingQuality = 'high'
  bctx.drawImage(small, 0, 0, big.width, big.height)
  return big
}
