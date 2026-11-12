import { motion } from "motion/react"
import { RotateCcwIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import type { Policy, Tier } from "@/lib/api"
import { TIER } from "@/lib/domain"

const BANDS: Tier[] = ["0", "1", "2", "3"]

export function StrictnessCard({
  policy,
  strictness,
  onChange,
  onCommit,
  onReset,
}: {
  policy: Policy | null
  strictness: number
  onChange: (v: number) => void
  onCommit: (v: number) => void
  onReset: () => void
}) {
  const [lo, hi] = policy?.strictness_range ?? [-30, 30]
  const thresholds = (policy?.base_thresholds ?? [20, 50, 70]).map((t) => t - strictness)
  const cuts = [0, ...thresholds.map((t) => Math.min(100, Math.max(0, t))), 100]

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Policy strictness</CardTitle>
        <CardDescription>One control for all three score thresholds.</CardDescription>
        <CardAction>
          <Button variant="ghost" size="sm" onClick={onReset}>
            <RotateCcwIcon /> Reset
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-4">
          <span className="text-xs text-muted-foreground">Lenient</span>
          <Slider
            aria-label="Strictness"
            min={lo}
            max={hi}
            step={1}
            value={[strictness]}
            onValueChange={([v]) => onChange(v)}
            onValueCommit={([v]) => onCommit(v)}
          />
          <span className="text-xs text-muted-foreground">Strict</span>
          <span className="w-12 rounded-md bg-muted py-1 text-center font-mono text-sm font-semibold tabular">
            {strictness > 0 ? `+${strictness}` : strictness}
          </span>
        </div>

        <div>
          <div className="flex h-2.5 overflow-hidden rounded-full">
            {BANDS.map((tier, i) => (
              <motion.div
                key={tier}
                className="h-full"
                style={{ backgroundColor: TIER[tier].color }}
                animate={{ width: `${cuts[i + 1] - cuts[i]}%` }}
                transition={{ type: "spring", stiffness: 200, damping: 28 }}
              />
            ))}
          </div>
          <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
            {BANDS.map((tier, i) => (
              <div key={tier} className="min-w-0">
                <div className="flex items-center gap-1.5 font-medium">
                  <span className="size-2 rounded-full" style={{ backgroundColor: TIER[tier].color }} />
                  {TIER[tier].short}
                </div>
                <div className="font-mono text-muted-foreground tabular">score {cuts[i]}+</div>
              </div>
            ))}
          </div>
        </div>
        <p className="font-mono text-xs text-muted-foreground">
          policy {policy?.policy_version ?? "…"} · thresholds {thresholds.join(" / ")}
        </p>
      </CardContent>
    </Card>
  )
}
