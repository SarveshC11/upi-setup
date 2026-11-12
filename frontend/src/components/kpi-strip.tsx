import { motion } from "motion/react"

import { AnimatedNumber } from "@/components/animated-number"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { BaselinePoint, Point } from "@/lib/api"

function Kpi({
  label,
  value,
  unit,
  decimals = 0,
  note,
  index,
  placeholder,
}: {
  label: string
  value: number | null
  unit?: string
  decimals?: number
  note?: React.ReactNode
  index: number
  placeholder?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35, ease: "easeOut" }}
    >
      <Card className="h-full justify-center gap-1.5 px-5 py-4">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {value === null && placeholder ? (
          <p className="font-mono text-[28px] leading-none font-semibold text-muted-foreground/50">{placeholder}</p>
        ) : value === null ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="font-mono text-[28px] leading-none font-semibold tracking-tight tabular">
            <AnimatedNumber value={value} decimals={decimals} />
            {unit && <span className="ml-1 text-sm font-medium text-muted-foreground">{unit}</span>}
          </p>
        )}
        <p className="text-xs text-muted-foreground">{note ?? " "}</p>
      </Card>
    </motion.div>
  )
}

export function KpiStrip({
  current,
  evasive,
  baselines,
  evasiveLoading = false,
}: {
  current: Point | null
  evasive: Point | null
  baselines: BaselinePoint[]
  evasiveLoading?: boolean
}) {
  const otp = baselines.find((b) => b.name === "always_strict")
  return (
    <div className="grid h-full grid-cols-2 gap-4">
      <Kpi index={0} label="Fraud value stopped" value={current?.prevented_pct ?? null} unit="%" decimals={1}
        note={otp && current ? `OTP on every payment: ${otp.prevented_pct.toFixed(1)}%` : undefined} />
      <Kpi index={1} label="Friction per 1,000 genuine" value={current?.friction ?? null} decimals={0}
        note={otp && current ? `${((current.friction / otp.friction) * 100).toFixed(0)}% of OTP-everywhere friction` : undefined} />
      <Kpi index={2} label="Genuine payments challenged" value={current ? current.extra / 10 : null} unit="%" decimals={1}
        note="Asked for anything beyond the PIN" />
      <Kpi index={3} label="Stopped, evasive attackers" value={evasive?.prevented_pct ?? null} unit="%" decimals={1}
        placeholder={evasiveLoading ? undefined : "—"}
        note={evasive ? "Attackers that try to look normal" : "Turn on evasive attackers to measure"} />
    </div>
  )
}
