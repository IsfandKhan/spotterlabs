import { useState } from "react"
import { MoonIcon, SunIcon } from "lucide-react"
import { useTheme } from "next-themes"
import { NavLink, Outlet } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { cn } from "@/lib/utils"

const FOCUS_RING =
  "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"

function NavItem({ to, children, end }: { to: string; children: React.ReactNode; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          FOCUS_RING,
          isActive ? "bg-secondary text-secondary-foreground" : "text-muted-foreground hover:text-foreground",
        )
      }
    >
      {children}
    </NavLink>
  )
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  // Seed from the class the inline script in index.html set, so the icon is
  // right on first paint (resolvedTheme is undefined until next-themes mounts).
  const [domDark] = useState(() => document.documentElement.classList.contains("dark"))
  const dark = resolvedTheme ? resolvedTheme === "dark" : domDark

  return (
    <button
      type="button"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(dark ? "light" : "dark")}
      className={cn(
        "grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:text-foreground",
        FOCUS_RING,
      )}
    >
      {dark ? <SunIcon className="size-4" /> : <MoonIcon className="size-4" />}
    </button>
  )
}

export function App() {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <NavLink to="/" className={cn("flex items-center gap-2 rounded-md", FOCUS_RING)}>
            <span className="grid size-7 place-items-center rounded-md bg-primary font-mono text-sm font-bold text-primary-foreground">
              E
            </span>
            <span className="text-sm font-semibold tracking-tight">ELD Trip Planner</span>
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavItem to="/" end>
              Plan a trip
            </NavItem>
            <NavItem to="/history">History</NavItem>
            <span className="mx-1 h-4 w-px bg-border" />
            <ThemeToggle />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-4 text-xs text-muted-foreground">
          Route + FMCSA hours-of-service logs. Property-carrying driver, 70&nbsp;hr / 8&nbsp;day. Not legal advice.
        </div>
      </footer>
      <Toaster position="top-center" />
    </div>
  )
}
