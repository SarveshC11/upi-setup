import { MoonIcon, SunIcon } from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"

export function AppHeader() {
  const { theme, setTheme } = useTheme()
  const dark =
    theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)

  return (
    <header className="border-b bg-card/70 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
        <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground shadow-sm">
          <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
            <path d="M4 18h3v-4H4zm6 0h3V9h-3zm6 0h3V5h-3z" fill="currentColor" />
          </svg>
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-[15px] leading-tight font-semibold tracking-tight">Step-up simulation engine</h1>
          <p className="truncate text-xs text-muted-foreground">
            Adaptive authentication for UPI-style payments · synthetic research build
          </p>
        </div>
        <div className="ml-auto">
          <Button
            variant="ghost"
            size="icon"
            aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
            onClick={() => setTheme(dark ? "light" : "dark")}
          >
            {dark ? <SunIcon /> : <MoonIcon />}
          </Button>
        </div>
      </div>
    </header>
  )
}
