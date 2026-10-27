import { useCallback, useRef, useState } from 'react'

import { api } from '../api/client'
import type { Heatmap, Plan, PlanRequest } from '../api/types'

interface State {
  plan: Plan | null
  planLoading: boolean
  planError: string | null
  heatmap: Heatmap | null
  heatLoading: boolean
  heatError: string | null
}

const INITIAL: State = {
  plan: null,
  planLoading: false,
  planError: null,
  heatmap: null,
  heatLoading: false,
  heatError: null,
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : 'Something went wrong'
}

/**
 * Plans a trip, then loads the corridor heatmap. Routes render as soon as the
 * plan arrives; the heatmap follows. A new submit aborts any in-flight requests.
 */
export function useTripPlanner() {
  const [state, setState] = useState<State>(INITIAL)
  const inflight = useRef<AbortController | null>(null)

  const submit = useCallback(async (req: PlanRequest) => {
    inflight.current?.abort()
    const ctrl = new AbortController()
    inflight.current = ctrl
    setState((s) => ({ ...s, planLoading: true, planError: null, heatError: null }))

    let plan: Plan
    try {
      plan = await api.plan(req, ctrl.signal)
    } catch (err) {
      if (ctrl.signal.aborted) return
      setState((s) => ({ ...s, planLoading: false, planError: message(err) }))
      return
    }
    setState({ ...INITIAL, plan, heatLoading: true })

    try {
      const lines = plan.routes.map((r) => r.geometry.map(([lon, lat]) => [lon, lat] as [number, number]))
      const heatmap = await api.heatmap(lines, req.load_lb, ctrl.signal)
      setState((s) => ({ ...s, heatmap, heatLoading: false }))
    } catch (err) {
      if (ctrl.signal.aborted) return
      setState((s) => ({ ...s, heatLoading: false, heatError: message(err) }))
    }
  }, [])

  return { ...state, submit }
}
