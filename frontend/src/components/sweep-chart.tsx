import { useReducedMotion } from "motion/react"
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, XAxis, YAxis } from "recharts"

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import type { Point } from "@/lib/api"

const config = {
  prevented_pct: { label: "Fraud value stopped (%)", color: "var(--chart-1)" },
  friction: { label: "Friction per 1,000 genuine", color: "var(--chart-2)" },
} satisfies ChartConfig

/** How fraud stopped and friction move as strictness changes. */
export function SweepChart({
  curve,
  strictness,
  range,
}: {
  curve: Point[]
  strictness: number
  range: [number, number]
}) {
  const animate = !useReducedMotion()
  const ticks = Array.from({ length: Math.floor((range[1] - range[0]) / 15) + 1 }, (_, i) => range[0] + i * 15)
  const data = curve
    .map((p) => ({ strictness: -p.shift, prevented_pct: +p.prevented_pct.toFixed(1), friction: Math.round(p.friction) }))
    .filter((p) => p.strictness >= range[0] && p.strictness <= range[1])
    .sort((a, b) => a.strictness - b.strictness)

  return (
    <ChartContainer config={config} className="aspect-auto h-[280px] w-full">
      <ComposedChart data={data} margin={{ top: 12, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="fillPrevented" x1="0" x2="0" y1="0" y2="1">
            <stop offset="5%" stopColor="var(--color-prevented_pct)" stopOpacity={0.28} />
            <stop offset="95%" stopColor="var(--color-prevented_pct)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 4" vertical={false} />
        <XAxis
          dataKey="strictness"
          type="number"
          domain={range}
          ticks={ticks}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v: number) => (v > 0 ? `+${v}` : `${v}`)}
        />
        <YAxis yAxisId="pct" domain={[0, 100]} tickLine={false} axisLine={false} width={40} tickFormatter={(v: number) => `${v}%`} />
        <YAxis yAxisId="fr" orientation="right" tickLine={false} axisLine={false} width={44} />
        <ChartTooltip
          content={<ChartTooltipContent indicator="line" labelFormatter={(_, p) => `Strictness ${p?.[0]?.payload?.strictness ?? ""}`} />}
        />
        <ChartLegend content={<ChartLegendContent />} />
        <Area
          yAxisId="pct"
          dataKey="prevented_pct"
          type="monotone"
          stroke="var(--color-prevented_pct)"
          strokeWidth={2.25}
          fill="url(#fillPrevented)"
          isAnimationActive={animate}
          animationDuration={900}
        />
        <Line
          yAxisId="fr"
          dataKey="friction"
          type="monotone"
          stroke="var(--color-friction)"
          strokeWidth={2}
          dot={false}
          isAnimationActive={animate}
          animationDuration={900}
        />
        <ReferenceLine
          yAxisId="pct"
          x={strictness}
          stroke="var(--foreground)"
          strokeOpacity={0.5}
          strokeDasharray="4 4"
          label={{ value: "now", position: "insideTopRight", className: "fill-muted-foreground text-[11px]" }}
        />
      </ComposedChart>
    </ChartContainer>
  )
}
