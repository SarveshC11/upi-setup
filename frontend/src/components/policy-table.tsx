import { motion } from "motion/react"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { BaselinePoint, Point } from "@/lib/api"
import { BASELINE_LABEL } from "@/lib/domain"
import { cn } from "@/lib/utils"

/** Engine at the current strictness against each simpler rule, on the same payments. */
export function PolicyTable({ current, baselines }: { current: Point; baselines: BaselinePoint[] }) {
  const rows = [
    { key: "engine", label: "This engine", ...current },
    ...baselines.map((b) => ({ key: b.name, label: BASELINE_LABEL[b.name] ?? b.name, ...b })),
  ]
  const best = Math.max(...rows.map((r) => r.prevented_pct))
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Policy</TableHead>
          <TableHead className="w-[40%]">Fraud stopped</TableHead>
          <TableHead className="text-right">Friction</TableHead>
          <TableHead className="text-right">Challenged</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={r.key} className={cn(r.key === "engine" && "bg-accent/50 font-medium")}>
            <TableCell className="whitespace-nowrap">{r.label}</TableCell>
            <TableCell>
              <div className="flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: r.key === "engine" ? "var(--chart-1)" : "var(--chart-4)" }}
                    initial={{ width: 0 }}
                    animate={{ width: `${(r.prevented_pct / Math.max(best, 1)) * 100}%` }}
                    transition={{ type: "spring", stiffness: 120, damping: 20, delay: i * 0.05 }}
                  />
                </div>
                <span className="w-14 text-right font-mono text-sm tabular">{r.prevented_pct.toFixed(1)}%</span>
              </div>
            </TableCell>
            <TableCell className="text-right font-mono tabular">{r.friction.toFixed(0)}</TableCell>
            <TableCell className="text-right font-mono tabular">{(r.extra / 10).toFixed(1)}%</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
