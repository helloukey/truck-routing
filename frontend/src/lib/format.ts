const timeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const clockFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })

export function formatTime(value: string | number | Date): string {
  return timeFmt.format(new Date(value))
}

/** Like formatTime without the zone, for dense tables (zone is shown once in the header). */
export function formatClock(value: string | number | Date): string {
  return clockFmt.format(new Date(value))
}

export const LOCAL_ZONE =
  new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts().find((p) => p.type === 'timeZoneName')
    ?.value ?? ''

export function formatDuration(seconds: number): string {
  const total = Math.round(seconds / 60)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h ? `${h}h ${m.toString().padStart(2, '0')}m` : `${m}m`
}

export function formatMiles(mi: number): string {
  return `${mi.toLocaleString(undefined, { maximumFractionDigits: mi < 10 ? 1 : 0 })} mi`
}

/** Route ids are display letters ("A", "B", "C"). */
export function routeName(id: string): string {
  return `Route ${id}`
}

/** Value for <input type="datetime-local"> at the next full hour, local time. */
export function nextHourLocalInput(): string {
  const d = new Date()
  d.setHours(d.getHours() + 1, 0, 0, 0)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`
}
