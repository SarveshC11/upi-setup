import { AnimatePresence, motion } from "motion/react"
import { ScanLineIcon } from "lucide-react"

import { AnimatedNumber } from "@/components/animated-number"
import { TierBadge } from "@/components/tier-badge"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import type { CompareResult, Tier } from "@/lib/api"
import { BASELINE_LABEL, SIGNAL_LABEL, TIER } from "@/lib/domain"
import { cn } from "@/lib/utils"

const BANDS: Tier[] = ["0", "1", "2", "3"]

export function DecisionCard({ result, stale }: { result: CompareResult | null; stale: boolean }) {
  if (!result) {
    return (
      <Card className="h-full">
        <CardContent className="grid h-full min-h-[420px] place-items-center text-center">
          <div className="grid max-w-xs justify-items-center gap-3">
            <div className="grid size-12 place-items-center rounded-full bg-muted">
              <ScanLineIcon className="size-5 text-muted-foreground" />
            </div>
            <p className="font-medium">No payment scored yet</p>
            <p className="text-sm text-muted-foreground">
              Pick a scenario or fill in the payment, then score it. The decision and the reason for it appear here.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const e = result.engine
  const cuts = [0, ...e.thresholds.map((t) => Math.min(100, Math.max(0, t))), 100]
  const color = TIER[e.tier].color
  const barMax = Math.max(40, ...e.breakdown.map((b) => b.points))

  return (
    <Card className={cn("h-full transition-opacity", stale && "opacity-60")}>
      <CardHeader>
        <CardTitle>Decision</CardTitle>
        <CardDescription className="font-mono text-xs">policy {e.policy_version}</CardDescription>
        <CardAction>
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={e.tier}
              initial={{ opacity: 0, scale: 0.8, y: -6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.8, y: 6 }}
              transition={{ type: "spring", stiffness: 380, damping: 24 }}
            >
              <TierBadge tier={e.tier} label={`Tier ${e.tier} · ${e.tier_name}`} className="px-3 py-1 text-[13px]" />
            </motion.div>
          </AnimatePresence>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-5">
        {stale && <p className="text-xs text-muted-foreground">Inputs changed. Score the payment again to update this decision.</p>}

        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Risk score</p>
            <p className="font-mono text-6xl leading-none font-semibold tracking-tighter tabular" style={{ color }}>
              <AnimatedNumber value={e.score} />
              <span className="ml-1 text-lg font-medium text-muted-foreground">/100</span>
            </p>
          </div>
          {e.raw_total > e.score && (
            <p className="text-right font-mono text-xs text-muted-foreground">raw total {e.raw_total}<br />capped at 100</p>
          )}
        </div>

        <div>
          <div className="relative">
            <div className="flex h-3 overflow-hidden rounded-full">
              {BANDS.map((tier, i) => (
                <motion.div
                  key={tier}
                  className="h-full"
                  style={{ backgroundColor: TIER[tier].color, opacity: tier === e.tier ? 1 : 0.35 }}
                  animate={{ width: `${cuts[i + 1] - cuts[i]}%` }}
                  transition={{ type: "spring", stiffness: 200, damping: 28 }}
                />
              ))}
            </div>
            <motion.div
              className="absolute -top-1.5 h-6 w-1.5 -translate-x-1/2 rounded-full bg-foreground ring-2 ring-card"
              initial={false}
              animate={{ left: `${Math.min(e.score, 100)}%` }}
              transition={{ type: "spring", stiffness: 170, damping: 20 }}
            />
          </div>
          <div className="relative mt-1.5 h-4 font-mono text-[10px] text-muted-foreground">
            {cuts.slice(1, 4).map((c, i) => (
              <span key={i} className="absolute -translate-x-1/2" style={{ left: `${c}%` }}>{c}</span>
            ))}
          </div>
        </div>

        <div className="grid gap-2">
          <p className="text-xs font-medium text-muted-foreground">Why: each signal's points</p>
          {e.breakdown.length === 0 && <p className="text-sm text-muted-foreground">No risk signals on this payment.</p>}
          <ul className="grid gap-2">
            <AnimatePresence initial={true}>
              {e.breakdown.map((b, i) => (
                <motion.li
                  key={`${b.signal}-${e.policy_version}`}
                  className="grid grid-cols-[minmax(0,10rem)_1fr_3rem] items-center gap-3 text-sm"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                >
                  <span className="truncate">{SIGNAL_LABEL[b.signal] ?? b.signal}</span>
                  <span className="h-2 overflow-hidden rounded-full bg-muted">
                    <motion.span
                      className="block h-full rounded-full"
                      style={{ backgroundColor: color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${(b.points / barMax) * 100}%` }}
                      transition={{ delay: 0.1 + i * 0.06, type: "spring", stiffness: 120, damping: 18 }}
                    />
                  </span>
                  <span className="text-right font-mono font-medium tabular">+{b.points}</span>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        </div>

        <div className="rounded-lg border-l-4 bg-muted/50 px-4 py-3 text-sm" style={{ borderLeftColor: color }}>
          <span className="font-medium">What the payer sees: </span>
          {TIER[e.tier].says}
        </div>

        <Separator />

        <div className="grid gap-2">
          <p className="text-xs font-medium text-muted-foreground">Same payment under the simpler rules</p>
          <div className="grid gap-1.5">
            {Object.entries(result.baselines).map(([name, t]) => (
              <div key={name} className="flex items-center justify-between text-sm">
                <span>{BASELINE_LABEL[name] ?? name}</span>
                <TierBadge tier={t} />
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
