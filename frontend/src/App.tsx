import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion } from "motion/react"
import { ActivityIcon, ListIcon, ScanLineIcon } from "lucide-react"

import { AppHeader } from "@/components/app-header"
import { DecisionCard } from "@/components/decision-card"
import { DecisionLog } from "@/components/decision-log"
import { KpiStrip } from "@/components/kpi-strip"
import { PaymentForm } from "@/components/payment-form"
import { SimulationPanel, type SimSettings } from "@/components/simulation-panel"
import { StrictnessCard } from "@/components/strictness-card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, type CompareResult, type Decision, type Payment, type Policy, type Simulation } from "@/lib/api"
import { PRESETS } from "@/lib/domain"

// Sweep every integer shift so the slider can read its point straight off the curve.
const SWEEP = { shift_start: -30, shift_stop: 60, shift_step: 1 }
const SWEEP_VIEW: [number, number] = [-60, 30]  // strictness = -shift

type Tab = "simulation" | "score" | "log"

export function App() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [policy, setPolicy] = useState<Policy | null>(null)
  const [strictness, setStrictness] = useState(0)
  const [tab, setTab] = useState<Tab>("simulation")

  const [settings, setSettings] = useState<SimSettings>({
    seed: 7, n_users: 300, payments_per_user: 30, attacks_per_type: 100, evasive: false,
  })
  const [sim, setSim] = useState<Simulation | null>(null)
  const [evasiveSim, setEvasiveSim] = useState<Simulation | null>(null)
  const [running, setRunning] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)

  const [payment, setPayment] = useState<Payment>(PRESETS["Chai stall"])
  const [preset, setPreset] = useState<string | null>(null)
  const [result, setResult] = useState<CompareResult | null>(null)
  const [stale, setStale] = useState(false)
  const [scoring, setScoring] = useState(false)
  const [scoreError, setScoreError] = useState<string | null>(null)

  const [decisions, setDecisions] = useState<Decision[]>([])
  const logRequest = useRef(0)

  const loadLog = useCallback(async () => {
    const mine = ++logRequest.current
    try {
      const { decisions } = await api.decisions(50)
      if (mine === logRequest.current) setDecisions(decisions)
    } catch {
      /* the log is a convenience view; the status badge already reports outages */
    }
  }, [])

  const runSim = useCallback(async (s: SimSettings) => {
    setRunning(true)
    setSimError(null)
    try {
      const base = { ...s, ...SWEEP }
      const [normal, evasive] = await Promise.all([
        api.simulate({ ...base, evasive: false }),
        s.evasive ? api.simulate({ ...base, evasive: true }) : Promise.resolve(null),
      ])
      setSim(normal)
      setEvasiveSim(evasive)
    } catch (err) {
      setSimError((err as Error).message)
    } finally {
      setRunning(false)
    }
  }, [])

  const score = useCallback(async (p: Payment) => {
    if (!(p.amount > 0) || !(p.median > 0)) {
      setScoreError("Enter an amount and a usual payment above ₹0.")
      return
    }
    setScoring(true)
    setScoreError(null)
    try {
      setResult(await api.compare(p))
      setStale(false)
      loadLog()
    } catch (err) {
      setScoreError((err as Error).message)
    } finally {
      setScoring(false)
    }
  }, [loadLog])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await api.health()
        const p = await api.policy()
        if (cancelled) return
        setOnline(true)
        setPolicy(p)
        setStrictness(-p.shift)
      } catch {
        if (!cancelled) setOnline(false)
        return
      }
      loadLog()
      runSim(settings)
      const linked = decodeURIComponent(location.hash.slice(1))
      if (PRESETS[linked]) {
        setTab("score")
        setPreset(linked)
        setPayment(PRESETS[linked])
        score(PRESETS[linked])
      }
    })()
    return () => {
      cancelled = true
    }
    // run once on load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const commitStrictness = async (v: number) => {
    try {
      setPolicy(await api.updatePolicy({ shift: -v }))
      if (result) score(payment)
    } catch (err) {
      setScoreError((err as Error).message)
    }
  }

  const resetPolicy = async () => {
    const p = await api.updatePolicy({ reset: true })
    setPolicy(p)
    setStrictness(-p.shift)
    if (result) score(payment)
  }

  const pointAt = (s: Simulation | null) =>
    s ? (s.curve.find((p) => p.shift === -strictness) ?? s.current) : null
  const current = useMemo(() => pointAt(sim), [sim, strictness]) // eslint-disable-line react-hooks/exhaustive-deps
  const evasiveCurrent = useMemo(() => pointAt(evasiveSim), [evasiveSim, strictness]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-svh bg-background">
      <AppHeader />

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6">
        {online === false && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm" role="alert">
            Cannot reach the decision service. Start it with <code className="font-mono">uvicorn service.api:app</code> and reload.
          </div>
        )}

        <section className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <StrictnessCard
            policy={policy}
            strictness={strictness}
            onChange={setStrictness}
            onCommit={commitStrictness}
            onReset={resetPolicy}
          />
          <KpiStrip
            current={current}
            evasive={evasiveCurrent}
            baselines={sim?.baselines ?? []}
            evasiveLoading={running && settings.evasive}
          />
        </section>

        <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="gap-4">
          <TabsList>
            <TabsTrigger value="simulation"><ActivityIcon /> Simulation</TabsTrigger>
            <TabsTrigger value="score"><ScanLineIcon /> Score a payment</TabsTrigger>
            <TabsTrigger value="log">
              <ListIcon /> Decision log
              {decisions.length > 0 && (
                <span className="rounded-full bg-muted px-1.5 font-mono text-[10px] tabular">{decisions.length}</span>
              )}
            </TabsTrigger>
          </TabsList>

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
            >
              <TabsContent value="simulation">
                <SimulationPanel
                  settings={settings}
                  onSettings={setSettings}
                  onRun={() => runSim(settings)}
                  running={running}
                  error={simError}
                  sim={sim}
                  evasiveSim={evasiveSim}
                  current={current}
                  strictness={strictness}
                  range={SWEEP_VIEW}
                />
              </TabsContent>
              <TabsContent value="score">
                <div className="grid items-start gap-4 lg:grid-cols-2">
                  <PaymentForm
                    payment={payment}
                    preset={preset}
                    policy={policy}
                    result={result}
                    busy={scoring}
                    error={scoreError}
                    onChange={(p) => {
                      setPayment(p)
                      setPreset(null)
                      if (result) setStale(true)
                    }}
                    onPreset={(name) => {
                      setPreset(name)
                      setPayment(PRESETS[name])
                      score(PRESETS[name])
                    }}
                    onScore={() => score(payment)}
                  />
                  <DecisionCard result={result} stale={stale} />
                </div>
              </TabsContent>
              <TabsContent value="log">
                <DecisionLog decisions={decisions} onRefresh={loadLog} />
              </TabsContent>
            </motion.div>
          </AnimatePresence>
        </Tabs>

        <footer className="pb-4 text-xs text-muted-foreground">
          All decisions come from the decision service API; this page only displays them. Tier 0 is the UPI PIN that every
          payment already needs; the engine only adds checks above it. Synthetic data, v1 placeholder numbers.
        </footer>
      </main>
    </div>
  )
}

export default App
