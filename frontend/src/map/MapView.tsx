import 'maplibre-gl/dist/maplibre-gl.css'
import './maplibreWorker'

import type { PickingInfo } from '@deck.gl/core'
import { BitmapLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import { useEffect, useMemo, useRef } from 'react'
import { Map, type MapRef, NavigationControl, useControl } from 'react-map-gl/maplibre'

import type { Checkpoint, Heatmap, Plan, Route } from '../api/types'
import { formatDuration, formatMiles, formatTime, routeName } from '../lib/format'
import { HEAT_VARIABLES, type HeatVariable, riskColor } from '../lib/risk'
import { type LonLat, departureMs, positionAt, riskSegments } from '../lib/track'
import { heatBounds, renderHeatFrame } from './heatmapImage'

const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const INITIAL_VIEW = { longitude: -96, latitude: 39, zoom: 3.6 }
const MUTED_ROUTE: [number, number, number] = [100, 116, 139]

export interface CheckpointRef {
  routeId: string
  index: number
}

interface Props {
  plan: Plan | null
  heatmap: Heatmap | null
  heatVariable: HeatVariable
  hour: number
  selectedId: string | null
  onSelect: (routeId: string) => void
  highlighted: CheckpointRef | null
}

interface CheckpointDatum extends Checkpoint {
  routeId: string
  index: number
}

function DeckOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props))
  overlay.setProps(props)
  return null
}

function checkpointTooltip(d: CheckpointDatum): string {
  const w = d.weather
  const risk = d.risk
  const rows = [
    `<b>${routeName(d.routeId)} · mile ${d.mile.toFixed(0)}</b>`,
    `ETA ${formatTime(d.eta)}`,
    w
      ? `Wind ${w.wind_mph.toFixed(0)} mph (gust ${w.gust_mph.toFixed(0)}) · Rain ${w.rain_in_hr.toFixed(2)} in/hr · Snow ${w.snow_in_hr.toFixed(2)} in/hr`
      : 'No forecast available for this ETA',
    risk ? `<b>Risk: ${risk.label}</b>` : '<b>Risk: unknown</b>',
    ...(risk?.reasons ?? []).map((r) => `• ${r}`),
  ]
  return rows.join('<br/>')
}

function routeTooltip(route: Route): string {
  const m = route.summary.miles_by_risk
  return [
    `<b>${routeName(route.id)}</b> · ${formatMiles(route.distance_mi)} · ${formatDuration(route.duration_s)}`,
    `Arrive ${formatTime(route.arrival)}`,
    `Severe+ ${(m.severe + m.no_travel).toFixed(0)} mi · High ${m.high.toFixed(0)} mi · Worst: ${route.summary.worst.label}`,
  ].join('<br/>')
}

export function MapView({ plan, heatmap, heatVariable, hour, selectedId, onSelect, highlighted }: Props) {
  const mapRef = useRef<MapRef>(null)

  // Fit the camera to new routes.
  useEffect(() => {
    if (!plan) return
    const [w, s, e, n] = plan.bounds
    mapRef.current?.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: { top: 60, bottom: 130, left: 60, right: 60 }, duration: 900 },
    )
  }, [plan])

  const checkpoints = useMemo<CheckpointDatum[]>(
    () =>
      plan?.routes.flatMap((r) => r.checkpoints.map((c, index) => ({ ...c, routeId: r.id, index }))) ??
      [],
    [plan],
  )

  // Geometry carries elapsed time as a 3rd value; strip it so deck.gl doesn't read it as elevation.
  const paths = useMemo(
    () => new globalThis.Map(plan?.routes.map((r) => [r.id, r.geometry.map(([lon, lat]) => [lon, lat] as LonLat)]) ?? []),
    [plan],
  )
  const endpoints = useMemo(() => {
    const g = plan?.routes[0]?.geometry
    return g ? [g[0], g[g.length - 1]] : []
  }, [plan])

  const selectedRoute = plan?.routes.find((r) => r.id === selectedId) ?? null
  const mutedRoutes = useMemo(() => plan?.routes.filter((r) => r.id !== selectedId) ?? [], [plan, selectedId])
  const selectedRoutes = useMemo(() => (selectedRoute ? [selectedRoute] : []), [selectedRoute])
  const selectedSegments = useMemo(() => (selectedRoute ? riskSegments(selectedRoute) : []), [selectedRoute])

  // Frames are rendered lazily and cached per (heatmap, variable), so scrubbing
  // back and forth never re-renders a frame.
  const getFrame = useMemo(() => {
    if (!heatmap) return null
    const cache = new globalThis.Map<number, HTMLCanvasElement>()
    return (h: number) => {
      let frame = cache.get(h)
      if (!frame) {
        frame = renderHeatFrame(heatmap.grid, heatmap[heatVariable][h], HEAT_VARIABLES[heatVariable].edges)
        cache.set(h, frame)
      }
      return frame
    }
  }, [heatmap, heatVariable])

  // Fractional hours cross-fade the two neighbouring hourly frames.
  const heatFrames = useMemo(() => {
    if (!heatmap || !getFrame) return null
    const last = heatmap.hours - 1
    const h0 = Math.min(Math.floor(hour), last)
    const h1 = Math.min(h0 + 1, last)
    return { base: getFrame(h0), next: getFrame(h1), mix: h1 === h0 ? 0 : hour - h0 }
  }, [heatmap, getFrame, hour])

  // Truck positions at the slider time.
  const trucks = useMemo(() => {
    if (!plan || !heatmap) return []
    const at = Date.parse(heatmap.start) + hour * 3_600_000
    return plan.routes.map((r) => {
      const elapsed = (at - departureMs(r)) / 1000
      return { route: r, position: positionAt(r.geometry, elapsed), enRoute: elapsed > 0 && elapsed < r.duration_s }
    })
  }, [plan, heatmap, hour])

  const layers = useMemo(() => {
    if (!plan) return []
    const highlightedCp = highlighted
      ? checkpoints.find((c) => c.routeId === highlighted.routeId && c.index === highlighted.index)
      : undefined
    const labelAnchor = (r: Route): LonLat => positionAt(r.geometry, r.duration_s / 2)

    return [
      heatmap &&
        heatFrames &&
        new BitmapLayer({
          id: 'heat-base',
          image: heatFrames.base,
          bounds: heatBounds(heatmap.grid),
          _imageCoordinateSystem: 'lnglat',
        }),
      heatmap &&
        heatFrames &&
        heatFrames.mix > 0 &&
        new BitmapLayer({
          id: 'heat-next',
          image: heatFrames.next,
          bounds: heatBounds(heatmap.grid),
          opacity: heatFrames.mix,
          _imageCoordinateSystem: 'lnglat',
        }),
      new PathLayer<Route>({
        id: 'routes-muted',
        data: mutedRoutes,
        getPath: (r) => paths.get(r.id) ?? [],
        getColor: [...MUTED_ROUTE, 200],
        getWidth: 5,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
        pickable: true,
        autoHighlight: true,
        highlightColor: [30, 58, 95, 220],
        onClick: ({ object }) => object && onSelect(object.id),
      }),
      new PathLayer({
        id: 'route-selected-casing',
        data: selectedRoutes,
        getPath: (r: Route) => paths.get(r.id) ?? [],
        getColor: [255, 255, 255, 255],
        getWidth: 10,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
      new PathLayer({
        id: 'route-selected-risk',
        data: selectedSegments,
        getPath: (s) => s.path,
        getColor: (s) => riskColor(s.level),
        getWidth: 6,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
      new ScatterplotLayer<CheckpointDatum>({
        id: 'checkpoints',
        data: checkpoints,
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: (d) => [...riskColor(d.risk?.level), d.routeId === selectedId ? 255 : 150],
        getLineColor: (d) => (d.routeId === selectedId ? [255, 255, 255, 255] : [255, 255, 255, 120]),
        getRadius: (d) => (d.routeId === selectedId ? 6 : 3.5),
        radiusUnits: 'pixels',
        stroked: true,
        lineWidthMinPixels: 1.5,
        pickable: true,
        updateTriggers: { getFillColor: selectedId, getLineColor: selectedId, getRadius: selectedId },
      }),
      new ScatterplotLayer({
        id: 'checkpoint-highlight',
        data: highlightedCp ? [highlightedCp] : [],
        getPosition: (d: CheckpointDatum) => [d.lon, d.lat],
        getFillColor: [0, 0, 0, 0],
        getLineColor: [17, 24, 39, 255],
        getRadius: 12,
        radiusUnits: 'pixels',
        stroked: true,
        lineWidthMinPixels: 3,
      }),
      new ScatterplotLayer({
        id: 'endpoints',
        data: endpoints,
        getPosition: (p) => [p[0], p[1]],
        getFillColor: (_, { index }) => (index === 0 ? [30, 58, 95, 255] : [17, 24, 39, 255]),
        getLineColor: [255, 255, 255, 255],
        getRadius: 8,
        radiusUnits: 'pixels',
        stroked: true,
        lineWidthMinPixels: 3,
      }),
      new ScatterplotLayer({
        id: 'trucks',
        data: trucks,
        getPosition: (t) => t.position,
        getFillColor: (t) => (t.route.id === selectedId ? [17, 24, 39, 255] : [71, 85, 105, 200]),
        getLineColor: (t) => (t.enRoute ? [245, 158, 11, 255] : [255, 255, 255, 255]),
        getRadius: (t) => (t.route.id === selectedId ? 9 : 7),
        radiusUnits: 'pixels',
        stroked: true,
        lineWidthMinPixels: 3,
        updateTriggers: { getFillColor: selectedId, getRadius: selectedId },
      }),
      new TextLayer<Route>({
        id: 'route-labels',
        data: plan.routes,
        getPosition: labelAnchor,
        getText: (r) =>
          `${routeName(r.id)}${r.id === plan.recommended_route_id ? ' ★' : ''}  ${formatMiles(r.distance_mi)} · ${formatDuration(r.duration_s)}`,
        characterSet: 'auto',
        getSize: 13,
        getColor: (r) => (r.id === selectedId ? [255, 255, 255, 255] : [30, 41, 59, 255]),
        background: true,
        getBackgroundColor: (r) => (r.id === selectedId ? [30, 58, 95, 240] : [255, 255, 255, 230]),
        backgroundPadding: [6, 3],
        fontFamily: 'system-ui, -apple-system, Segoe UI, sans-serif',
        fontWeight: 600,
        getPixelOffset: [0, -18],
        pickable: true,
        onClick: ({ object }) => object && onSelect(object.id),
        updateTriggers: { getColor: selectedId, getBackgroundColor: selectedId },
      }),
    ].filter(Boolean)
  }, [
    plan,
    heatmap,
    heatFrames,
    selectedId,
    mutedRoutes,
    selectedRoutes,
    selectedSegments,
    checkpoints,
    trucks,
    highlighted,
    paths,
    endpoints,
    onSelect,
  ])

  const getTooltip = ({ object, layer }: PickingInfo) => {
    if (!object || !layer) return null
    if (layer.id === 'checkpoints') return { html: checkpointTooltip(object as CheckpointDatum), className: 'map-tooltip' }
    if (layer.id === 'routes-muted' || layer.id === 'route-labels') {
      const r = object as Route
      return { html: routeTooltip(r), className: 'map-tooltip' }
    }
    return null
  }

  return (
    <Map ref={mapRef} initialViewState={INITIAL_VIEW} mapStyle={BASEMAP} style={{ width: '100%', height: '100%' }}>
      <NavigationControl position="top-right" showCompass={false} />
      <DeckOverlay layers={layers} getTooltip={getTooltip} />
    </Map>
  )
}
