import { useReducedMotion } from "motion/react"
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  Scatter,
  XAxis,
  YAxis,
} from "recharts"

import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import type { BaselinePoint, Point } from "@/lib/api"
import { BASELINE_LABEL } from "@/lib/domain"

const config = {
  engine: { label: "Engine", color: "var(--chart-1)" },
  evasive: { label: "Engine vs evasive attackers", color: "var(--chart-2)" },
  baseline: { label: "Simpler rules", color: "var(--chart-4)" },
} satisfies ChartConfig

const TICKS = [0, 10, 50, 100, 250, 500, 1000, 1500, 2000]

type Hover = Partial<Point> & { label?: string; series?: string }

function TradeoffTooltip({ active, payload }: { active?: boolean; payload?: { payload: Hover }[] }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="grid min-w-44 gap-1.5 rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
      <div className="font-medium">
        {d.label ?? `${d.series ?? "Engine"} · strictness ${d.shift !== undefined ? -d.shift : ""}`}
      </div>
      <Row k="Fraud value stopped" v={`${d.prevented_pct?.toFixed(1)}%`} />
      <Row k="Friction / 1,000 genuine" v={d.friction?.toFixed(0) ?? ""} />
      <Row k="Genuine challenged" v={`${((d.extra ?? 0) / 10).toFixed(1)}%`} />
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono font-medium tabular">{v}</span>
    </div>
  )
}

export function TradeoffChart({
  curve,
  evasive,
  baselines,
  current,
}: {
  curve: Point[]
  evasive: Point[] | null
  baselines: BaselinePoint[]
  current: Point
}) {
  const sorted = [...curve].sort((a, b) => a.friction - b.friction).map((p) => ({ ...p, series: "Engine" }))
  const evSorted = evasive
    ? [...evasive].sort((a, b) => a.friction - b.friction).map((p) => ({ ...p, series: "Evasive" }))
    : null
  const animate = !useReducedMotion()
  // Baselines often sit close together near the origin; stagger their labels vertically.
  const base = [...baselines]
    .sort((a, b) => b.prevented_pct - a.prevented_pct)
    .map((b, i, arr) => {
      const near = i > 0 && Math.abs(arr[i - 1].prevented_pct - b.prevented_pct) < 6
        && Math.abs(Math.sqrt(arr[i - 1].friction) - Math.sqrt(b.friction)) < 6
      return { ...b, label: BASELINE_LABEL[b.name] ?? b.name, dy: near ? 16 : -2 }
    })
  const maxF = Math.max(100, ...curve.map((p) => p.friction), ...baselines.map((b) => b.friction))
  const ticks = TICKS.filter((t) => t <= maxF)

  return (
    <ChartContainer config={config} className="aspect-auto h-[360px] w-full sm:h-[400px]">
      <ComposedChart margin={{ top: 24, right: 28, bottom: 8, left: 0 }}>
        <defs>
          <linearGradient id="engineGlow" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="var(--color-engine)" stopOpacity={0.55} />
            <stop offset="100%" stopColor="var(--color-engine)" stopOpacity={1} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 4" vertical={false} />
        <XAxis
          type="number"
          dataKey="friction"
          scale="sqrt"
          domain={[0, maxF]}
          ticks={ticks}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v: number) => v.toLocaleString("en-IN")}
          label={{ value: "Friction per 1,000 genuine payments (√ scale)", position: "insideBottom", offset: -4, className: "fill-muted-foreground text-[11px]" }}
          height={44}
        />
        <YAxis
          type="number"
          dataKey="prevented_pct"
          domain={[0, 100]}
          ticks={[0, 20, 40, 60, 80, 100]}
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={(v: number) => `${v}%`}
        />
        <ChartTooltip cursor={{ strokeDasharray: "3 3" }} content={<TradeoffTooltip />} />
        {evSorted && (
          <Line
            data={evSorted}
            dataKey="prevented_pct"
            name="evasive"
            type="monotone"
            stroke="var(--color-evasive)"
            strokeWidth={2}
            strokeDasharray="6 5"
            dot={false}
            activeDot={{ r: 4 }}
            isAnimationActive={animate}
            animationDuration={900}
          />
        )}
        <Line
          data={sorted}
          dataKey="prevented_pct"
          name="engine"
          type="monotone"
          stroke="url(#engineGlow)"
          strokeWidth={2.75}
          dot={false}
          activeDot={{ r: 5, fill: "var(--color-engine)", stroke: "var(--background)", strokeWidth: 2 }}
          isAnimationActive={animate}
          animationDuration={1100}
        />
        <Scatter
          data={base}
          dataKey="prevented_pct"
          name="baseline"
          fill="var(--color-baseline)"
          isAnimationActive={animate}
          shape={(props: { cx?: number; cy?: number; payload?: { label: string; dy: number; friction: number } }) => {
            const cx = props.cx ?? 0
            const cy = props.cy ?? 0
            const flip = (props.payload?.friction ?? 0) > maxF * 0.55
            return (
              <g>
                <rect x={cx - 5} y={cy - 5} width={10} height={10} rx={2} fill="var(--color-baseline)" />
                <text
                  x={flip ? cx - 10 : cx + 10}
                  y={cy + 4 + (props.payload?.dy ?? 0)}
                  textAnchor={flip ? "end" : "start"}
                  className="fill-muted-foreground text-[11px]"
                >
                  {props.payload?.label}
                </text>
              </g>
            )
          }}
        />
        <ReferenceDot
          x={current.friction}
          y={current.prevented_pct}
          r={8}
          fill="var(--color-engine)"
          stroke="var(--background)"
          strokeWidth={3}
          ifOverflow="visible"
          label={{
            value: `Current · ${current.prevented_pct.toFixed(1)}%`,
            position: "top",
            offset: 14,
            className: "fill-foreground text-xs font-semibold",
          }}
        />
      </ComposedChart>
    </ChartContainer>
  )
}
