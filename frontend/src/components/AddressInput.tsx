import * as React from "react"

import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/**
 * Address field with a Google-Maps-style autocomplete panel. Suggestions come
 * from Photon (photon.komoot.io) — same OSM data as our geocoder, no API key,
 * CORS-open. Rendered as a custom listbox (not a native <datalist>) so it can be
 * full input width with two-line results and proper keyboard nav.
 */

const MIN_CHARS = 3
const DEBOUNCE_MS = 250
// Bias toward the US (geographic centroid) without hard-filtering.
const ENDPOINT = "https://photon.komoot.io/api/?limit=6&lang=en&lat=39.8&lon=-98.6&q="

type PhotonProps = Record<string, string | undefined>
export type Suggestion = { primary: string; secondary: string; value: string }

// ponytail: naive formatter — primary = name/street/city, secondary = the rest.
// `value` (submitted + re-geocoded server-side) is the two joined.
export function suggestionFrom(p: PhotonProps): Suggestion {
  const street = [p.housenumber, p.street].filter(Boolean).join(" ")
  const primary = p.name || street || p.city || p.state || "Unknown place"
  const rest = [
    street && street !== primary ? street : undefined,
    p.city && p.city !== primary ? p.city : undefined,
    p.state && p.state !== primary ? p.state : undefined,
    p.countrycode && p.countrycode !== "US" ? p.country : undefined,
  ].filter(Boolean) as string[]
  const secondary = [...new Set(rest)].join(", ")
  return { primary, secondary, value: secondary ? `${primary}, ${secondary}` : primary }
}

type Props = Omit<React.ComponentProps<typeof Input>, "value" | "onChange"> & {
  value: string
  onValueChange: (value: string) => void
}

export function AddressInput({ value, onValueChange, id, className, ...props }: Props) {
  const listboxId = React.useId()
  const rootRef = React.useRef<HTMLDivElement>(null)
  const justPicked = React.useRef(false)
  const [items, setItems] = React.useState<Suggestion[]>([])
  const [open, setOpen] = React.useState(false)
  const [active, setActive] = React.useState(-1)

  React.useEffect(() => {
    if (justPicked.current) {
      justPicked.current = false
      return
    }
    const q = value.trim()
    if (q.length < MIN_CHARS) {
      setItems([])
      setOpen(false)
      return
    }
    const ctl = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const resp = await fetch(ENDPOINT + encodeURIComponent(q), { signal: ctl.signal })
        const data = await resp.json()
        const seen = new Set<string>()
        const next: Suggestion[] = []
        for (const f of data.features ?? []) {
          const s = suggestionFrom(f.properties ?? {})
          if (s.value && !seen.has(s.value)) {
            seen.add(s.value)
            next.push(s)
          }
        }
        setItems(next)
        setActive(-1)
        setOpen(next.length > 0)
      } catch {
        // aborted or offline — keep the last suggestions
      }
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      ctl.abort()
    }
  }, [value])

  React.useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("pointerdown", onDown)
    return () => document.removeEventListener("pointerdown", onDown)
  }, [open])

  function pick(s: Suggestion) {
    justPicked.current = true
    onValueChange(s.value)
    setItems([])
    setOpen(false)
    setActive(-1)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" && !open && items.length) {
      setOpen(true)
      return
    }
    if (!open || !items.length) return
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActive((i) => (i + 1) % items.length)
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActive((i) => (i <= 0 ? items.length - 1 : i - 1))
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault()
      pick(items[active])
    } else if (e.key === "Escape") {
      setOpen(false)
      setActive(-1)
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <Input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listboxId}-opt-${active}` : undefined}
        autoComplete="off"
        className={className}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => items.length > 0 && setOpen(true)}
        {...props}
      />
      {open && items.length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-border bg-popover py-1 text-popover-foreground shadow-md"
        >
          {items.map((s, i) => (
            <li
              key={s.value}
              id={`${listboxId}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              onPointerDown={(e) => {
                e.preventDefault()
                pick(s)
              }}
              onPointerEnter={() => setActive(i)}
              className={cn(
                "cursor-pointer px-3 py-1.5",
                i === active && "bg-accent text-accent-foreground",
              )}
            >
              <div className="truncate text-sm font-medium">{s.primary}</div>
              {s.secondary && (
                <div className="truncate text-xs text-muted-foreground">{s.secondary}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
