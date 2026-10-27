import type { Heatmap, Place, Plan, PlanRequest } from './types'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** DRF errors are either {detail} or {field: [messages]}; flatten to one line. */
function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const b = body as Record<string, unknown>
    if (typeof b.detail === 'string') return b.detail
    const parts = Object.entries(b).map(([field, msgs]) => {
      const text = Array.isArray(msgs) ? msgs.join(' ') : JSON.stringify(msgs)
      return field === 'non_field_errors' ? text : `${field.replace('_', ' ')}: ${text}`
    })
    if (parts.length) return parts.join(' · ')
  }
  return `Request failed (${status})`
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.status))
  return body as T
}

export const api = {
  geocode: (q: string, signal?: AbortSignal) =>
    request<{ results: Place[] }>(`/geocode?q=${encodeURIComponent(q)}`, { signal }).then((r) => r.results),

  plan: (req: PlanRequest, signal?: AbortSignal) =>
    request<Plan>('/plan', { method: 'POST', body: JSON.stringify(req), signal }),

  heatmap: (lines: [number, number][][], loadLb: number, signal?: AbortSignal) =>
    request<Heatmap>('/heatmap', {
      method: 'POST',
      body: JSON.stringify({ lines, load_lb: loadLb }),
      signal,
    }),
}
