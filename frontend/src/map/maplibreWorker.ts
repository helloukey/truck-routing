// MapLibre 6 locates its worker relative to its own module URL, which breaks once
// Vite pre-bundles (dev) or chunks (build) the library. Let Vite bundle the worker
// and hand MapLibre the resulting URL instead.
import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

setWorkerUrl(workerUrl)
