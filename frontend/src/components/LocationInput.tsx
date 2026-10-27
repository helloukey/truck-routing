import { useEffect, useId, useState } from 'react'

import { api } from '../api/client'
import type { Place } from '../api/types'

const DEBOUNCE_MS = 300
const MIN_CHARS = 3

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  placeholder?: string
}

/** Address autocomplete backed by /api/geocode (accessible combobox pattern). */
export function LocationInput({ label, value, onChange, placeholder }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [error, setError] = useState<string | null>(null)

  // Keep the text in sync when the parent sets a place (e.g. "Try an example").
  const [syncedValue, setSyncedValue] = useState(value)
  if (value !== syncedValue) {
    setSyncedValue(value)
    if (value) setText(value.label)
  }

  const query = text.trim()
  const searching = query.length >= MIN_CHARS && query !== value?.label

  useEffect(() => {
    if (!searching) return
    const ctrl = new AbortController()
    const timer = setTimeout(() => {
      api
        .geocode(query, ctrl.signal)
        .then((r) => {
          setResults(r)
          setActive(-1)
          setError(null)
        })
        .catch(() => !ctrl.signal.aborted && setError('Location search unavailable'))
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [query, searching])

  const choose = (place: Place) => {
    onChange(place)
    setText(place.label)
    setOpen(false)
  }

  const suggestions = searching ? results : []

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!suggestions.length) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((a) => (a + 1) % suggestions.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => (a <= 0 ? suggestions.length - 1 : a - 1))
    } else if (e.key === 'Enter' && open && active >= 0) {
      e.preventDefault()
      choose(suggestions[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && suggestions.length > 0

  return (
    <div className="field location">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        role="combobox"
        aria-expanded={showList}
        aria-controls={`${id}-list`}
        aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
        autoComplete="off"
        value={text}
        placeholder={placeholder}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
          if (value) onChange(null)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul id={`${id}-list`} role="listbox" className="suggestions">
          {suggestions.map((r, i) => (
            <li
              key={`${r.lat},${r.lon}`}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : undefined}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(r)
              }}
            >
              {r.label}
            </li>
          ))}
        </ul>
      )}
      {error && <span className="field-hint error-text">{error}</span>}
    </div>
  )
}
