import { Loader2Icon, ScanLineIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Network, Payment, Policy } from "@/lib/api"
import { FLAGS, FRI_LEVELS, NETWORKS, PRESETS, inr } from "@/lib/domain"
import { cn } from "@/lib/utils"

export function PaymentForm({
  payment,
  preset,
  policy,
  busy,
  error,
  onChange,
  onPreset,
  onScore,
}: {
  payment: Payment
  preset: string | null
  policy: Policy | null
  busy: boolean
  error: string | null
  onChange: (p: Payment) => void
  onPreset: (name: string) => void
  onScore: () => void
}) {
  const pts = (key: string | null) => (key && policy ? `+${policy.weights[key]}` : "+0")
  const ratio = payment.amount > 0 && payment.median > 0 ? payment.amount / payment.median : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Payment</CardTitle>
        <CardDescription>Start from a scenario or describe a payment. Points show what each signal adds.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-5"
          onSubmit={(e) => {
            e.preventDefault()
            onScore()
          }}
        >
          <div className="grid gap-2">
            <Label>Scenario</Label>
            <div className="flex flex-wrap gap-2">
              {Object.keys(PRESETS).map((name) => (
                <Button
                  key={name}
                  type="button"
                  size="sm"
                  variant={preset === name ? "default" : "outline"}
                  className="rounded-full"
                  aria-pressed={preset === name}
                  onClick={() => onPreset(name)}
                >
                  {name}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <MoneyField id="amount" label="Amount" value={payment.amount} onChange={(v) => onChange({ ...payment, amount: v })} />
            <MoneyField id="median" label="Payer's usual payment" value={payment.median} onChange={(v) => onChange({ ...payment, median: v })} />
          </div>
          <p className="-mt-2 font-mono text-xs text-muted-foreground" aria-live="polite">
            {ratio !== null ? (
              <>₹{inr(payment.amount)} is <b className="text-foreground">{inr(ratio, ratio < 10 ? 2 : 0)}×</b> this payer's usual payment</>
            ) : (
              "Enter both amounts to see how unusual the payment is."
            )}
          </p>

          <div className="grid gap-2">
            <Label>Network</Label>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              className="w-full"
              value={payment.network}
              onValueChange={(v) => v && onChange({ ...payment, network: v as Network })}
            >
              {NETWORKS.map((n) => (
                <ToggleGroupItem key={n.value} value={n.value} className="flex-1 gap-1.5">
                  {n.label} <span className="font-mono text-[10px] opacity-60">{pts(n.weight)}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <div className="grid gap-2">
            <Label>Payee number risk (DoT FRI)</Label>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              className="w-full"
              value={String(payment.fri)}
              onValueChange={(v) => v && onChange({ ...payment, fri: Number(v) })}
            >
              {FRI_LEVELS.map((f) => (
                <ToggleGroupItem key={f.value} value={String(f.value)} className="flex-1 gap-1.5">
                  {f.label} <span className="hidden font-mono text-[10px] opacity-60 sm:inline">{pts(f.weight)}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <div className="grid gap-2">
            <Label>Signals seen on this payment</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {FLAGS.map((f) => {
                const on = payment[f.field]
                return (
                  <label
                    key={f.field}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors",
                      on ? "border-primary/50 bg-accent" : "hover:bg-muted/60"
                    )}
                  >
                    <Switch checked={on} onCheckedChange={(v) => onChange({ ...payment, [f.field]: v })} />
                    <span className="flex-1 leading-tight">{f.label}</span>
                    <span className={cn("font-mono text-xs", on ? "text-foreground" : "text-muted-foreground")}>{pts(f.weight)}</span>
                  </label>
                )
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2Icon className="animate-spin" /> : <ScanLineIcon />}
              Score payment
            </Button>
            {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function MoneyField({ id, label, value, onChange }: { id: string; label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted-foreground">₹</span>
        <Input
          id={id}
          type="number"
          min={1}
          step="any"
          inputMode="decimal"
          className="h-10 pl-7 font-mono text-base font-semibold tabular"
          value={Number.isFinite(value) ? value : ""}
          onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
        />
      </div>
    </div>
  )
}
