import { useState } from "react"
import { ArrowUpRightIcon, ChevronLeftIcon, Loader2Icon, MoreHorizontalIcon, ScanLineIcon, ShieldCheckIcon, SmartphoneIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { CompareResult, Network, Payment, Policy } from "@/lib/api"
import { FLAGS, FRI_LEVELS, NETWORKS, PRESETS, inr } from "@/lib/domain"
import { cn } from "@/lib/utils"

export function PaymentForm({
  payment,
  preset,
  policy,
  result,
  busy,
  error,
  onChange,
  onPreset,
  onScore,
}: {
  payment: Payment
  preset: string | null
  policy: Policy | null
  result: CompareResult | null
  busy: boolean
  error: string | null
  onChange: (p: Payment) => void
  onPreset: (name: string) => void
  onScore: () => void
}) {
  const [phoneMode, setPhoneMode] = useState(true)
  const pts = (key: string | null) => (key && policy ? `+${policy.weights[key]}` : "+0")
  const ratio = payment.amount > 0 && payment.median > 0 ? payment.amount / payment.median : null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{phoneMode ? "Try a payment" : "Payment details"}</CardTitle>
            <CardDescription>
              {phoneMode ? "Use the checkout below as a customer would." : "Adjust the signals used by the risk engine."}
            </CardDescription>
          </div>
          <div className="flex rounded-lg border bg-muted/40 p-0.5">
            <Button type="button" size="sm" variant={phoneMode ? "secondary" : "ghost"} className="h-8 gap-1.5 px-2.5 text-xs" onClick={() => setPhoneMode(true)}>
              <SmartphoneIcon className="size-3.5" /> Phone
            </Button>
            <Button type="button" size="sm" variant={!phoneMode ? "secondary" : "ghost"} className="h-8 px-2.5 text-xs" onClick={() => setPhoneMode(false)}>
              Details
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {phoneMode ? (
          <PhoneCheckout
            payment={payment}
            result={result}
            busy={busy}
            error={error}
            onAmount={(amount) => onChange({ ...payment, amount })}
            onScore={onScore}
            onDetails={() => setPhoneMode(false)}
          />
        ) : (
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
        )}
      </CardContent>
    </Card>
  )
}

function PhoneCheckout({
  payment,
  result,
  busy,
  error,
  onAmount,
  onScore,
  onDetails,
}: {
  payment: Payment
  result: CompareResult | null
  busy: boolean
  error: string | null
  onAmount: (amount: number) => void
  onScore: () => void
  onDetails: () => void
}) {
  const tier = result?.engine.tier
  return (
    <div className="grid gap-4">
      <div className="mx-auto w-full max-w-[310px] rounded-[2rem] border-[7px] border-foreground/90 bg-foreground p-1.5 shadow-xl shadow-foreground/10">
        <div className="overflow-hidden rounded-[1.45rem] bg-background">
          <div className="flex items-center justify-between bg-card px-4 py-2 text-[10px] text-muted-foreground">
            <span>9:41</span><span className="font-medium">UPI Secure</span><span>● ● ▰</span>
          </div>
          <div className="border-b bg-card px-4 py-3">
            <div className="flex items-center justify-between">
              <ChevronLeftIcon className="size-4" />
              <span className="text-xs font-medium">Confirm payment</span>
              <MoreHorizontalIcon className="size-4" />
            </div>
          </div>
          <div className="grid gap-5 px-5 py-7">
            <div className="grid justify-items-center gap-2">
              <div className="grid size-14 place-items-center rounded-2xl bg-primary/10 text-primary">
                <ArrowUpRightIcon className="size-6" />
              </div>
              <p className="text-sm font-semibold">Ravi Grocery Store</p>
              <p className="text-xs text-muted-foreground">ravi.grocery@upi</p>
            </div>
            <div className="grid gap-1 text-center">
              <label htmlFor="phone-amount" className="text-[11px] text-muted-foreground">Amount to pay</label>
              <div className="flex items-center justify-center">
                <span className="text-2xl text-muted-foreground">₹</span>
                <input
                  id="phone-amount"
                  type="number"
                  min={1}
                  inputMode="decimal"
                  value={Number.isFinite(payment.amount) ? payment.amount : ""}
                  onChange={(e) => onAmount(e.target.value === "" ? NaN : Number(e.target.value))}
                  className="w-36 bg-transparent text-center font-mono text-4xl font-semibold tracking-tight outline-none"
                  aria-label="Payment amount"
                />
              </div>
              <p className="text-[11px] text-muted-foreground">From HDFC Bank •••• 1842</p>
            </div>
            <Button type="button" className="h-11 w-full rounded-xl" disabled={busy} onClick={onScore}>
              {busy ? <Loader2Icon className="animate-spin" /> : <ShieldCheckIcon />}
              {busy ? "Checking payment…" : "Pay securely"}
            </Button>
            {tier && (
              <div className="rounded-xl border bg-muted/50 px-3 py-2.5 text-center text-xs">
                <span className="font-medium">Bank check required: </span>{result.engine.tier_name}
              </div>
            )}
          </div>
          <div className="border-t px-4 py-3 text-center text-[10px] text-muted-foreground">
            Protected by the UPI Step-up Engine
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2.5 text-xs">
        <span className="text-muted-foreground">Need to test a specific fraud signal?</span>
        <Button type="button" variant="outline" size="sm" onClick={onDetails}>Open payment details</Button>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
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
