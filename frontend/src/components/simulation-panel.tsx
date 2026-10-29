import { AnimatePresence, motion } from "motion/react"
import { Loader2Icon, PlayIcon } from "lucide-react"

import { PolicyTable } from "@/components/policy-table"
import { SweepChart } from "@/components/sweep-chart"
import { TradeoffChart } from "@/components/tradeoff-chart"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import type { Point, Simulation } from "@/lib/api"

export interface SimSettings {
  seed: number
  n_users: number
  payments_per_user: number
  attacks_per_type: number
  evasive: boolean
}

const FIELDS: { key: keyof Omit<SimSettings, "evasive">; label: string; hint: string }[] = [
  { key: "seed", label: "Seed", hint: "Same seed, same payments" },
  { key: "n_users", label: "Users", hint: "Service limit 300" },
  { key: "payments_per_user", label: "Payments per user", hint: "Service limit 30" },
  { key: "attacks_per_type", label: "Attacks per type", hint: "5 attack types, limit 100" },
]

export function SimulationPanel({
  settings,
  onSettings,
  onRun,
  running,
  error,
  sim,
  evasiveSim,
  current,
  strictness,
  range,
}: {
  settings: SimSettings
  onSettings: (s: SimSettings) => void
  onRun: () => void
  running: boolean
  error: string | null
  sim: Simulation | null
  evasiveSim: Simulation | null
  current: Point | null
  strictness: number
  range: [number, number]
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      <Card className="h-fit lg:sticky lg:top-4">
        <CardHeader>
          <CardTitle>Run settings</CardTitle>
          <CardDescription>Generates synthetic genuine payments and five labelled attack types, then sweeps strictness.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault()
              onRun()
            }}
          >
            {FIELDS.map((f) => (
              <div key={f.key} className="grid gap-1.5">
                <Label htmlFor={`sim-${f.key}`}>{f.label}</Label>
                <Input
                  id={`sim-${f.key}`}
                  type="number"
                  min={f.key === "seed" ? undefined : 1}
                  className="font-mono tabular"
                  value={settings[f.key]}
                  onChange={(e) => onSettings({ ...settings, [f.key]: Number(e.target.value) })}
                />
                <p className="text-[11px] text-muted-foreground">{f.hint}</p>
              </div>
            ))}
            <Separator />
            <label className="flex items-start justify-between gap-3">
              <span className="grid gap-0.5">
                <span className="text-sm font-medium">Evasive attackers</span>
                <span className="text-[11px] text-muted-foreground">Also run attackers that hide their usual signals</span>
              </span>
              <Switch
                checked={settings.evasive}
                onCheckedChange={(v) => onSettings({ ...settings, evasive: v })}
                aria-label="Evasive attackers"
              />
            </label>
            <Button type="submit" disabled={running} className="w-full">
              {running ? <Loader2Icon className="animate-spin" /> : <PlayIcon />}
              {running ? "Running simulation…" : "Run simulation"}
            </Button>
            {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
            {sim && (
              <p className="font-mono text-[11px] leading-relaxed text-muted-foreground">
                {sim.n_legit.toLocaleString("en-IN")} genuine · {sim.n_attacks.toLocaleString("en-IN")} attacks
                <br />
                {sim.curve.length} strictness levels · {(sim.elapsed_ms + (evasiveSim?.elapsed_ms ?? 0)).toFixed(0)} ms
              </p>
            )}
          </form>
        </CardContent>
      </Card>

      <div className="grid min-w-0 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Fraud stopped versus friction</CardTitle>
            <CardDescription>
              The line is the engine across every strictness level; squares are the simpler rules on the same payments.
              Higher and further left is better.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartFrame ready={Boolean(sim && current)} running={running} height="h-[360px] sm:h-[400px]">
              {sim && current && (
                <TradeoffChart curve={sim.curve} evasive={evasiveSim?.curve ?? null} baselines={sim.baselines} current={current} />
              )}
            </ChartFrame>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-muted-foreground">
              <LegendItem swatch={<span className="h-0.5 w-5 rounded bg-chart-1" />} label="Engine, strictness sweep" />
              {evasiveSim && (
                <LegendItem swatch={<span className="w-5 border-t-2 border-dashed border-chart-2" />} label="Engine vs evasive attackers" />
              )}
              <LegendItem swatch={<span className="size-2.5 rounded-[2px] bg-chart-4" />} label="Simpler rules" />
              <LegendItem swatch={<span className="size-2.5 rounded-full bg-chart-1 ring-2 ring-background" />} label="Current strictness" />
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 2xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>What strictness does</CardTitle>
              <CardDescription>Fraud stopped and friction at every slider position.</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartFrame ready={Boolean(sim)} running={running} height="h-[280px]">
                {sim && <SweepChart curve={sim.curve} strictness={strictness} range={range} />}
              </ChartFrame>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Policy comparison</CardTitle>
              <CardDescription>Same synthetic payments and the same luck for every policy. Friction is per 1,000 genuine payments.</CardDescription>
            </CardHeader>
            <CardContent>
              {sim && current ? <PolicyTable current={current} baselines={sim.baselines} /> : <Skeleton className="h-[240px] w-full" />}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function LegendItem({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      {swatch}
      {label}
    </span>
  )
}

function ChartFrame({
  ready,
  running,
  height,
  children,
}: {
  ready: boolean
  running: boolean
  height: string
  children: React.ReactNode
}) {
  return (
    <div className="relative">
      {ready ? children : <Skeleton className={`${height} w-full`} />}
      <AnimatePresence>
        {running && ready && (
          <motion.div
            className="absolute inset-0 grid place-items-center rounded-lg bg-card/60 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <span className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs shadow-sm">
              <Loader2Icon className="size-3.5 animate-spin" /> Simulating
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
