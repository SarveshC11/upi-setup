import { AnimatePresence, motion } from "motion/react"
import { RefreshCwIcon } from "lucide-react"

import { TierBadge } from "@/components/tier-badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Decision } from "@/lib/api"
import { SIGNAL_LABEL, inr } from "@/lib/domain"

export function DecisionLog({ decisions, onRefresh }: { decisions: Decision[]; onRefresh: () => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Decision log</CardTitle>
        <CardDescription>
          Every scored payment, newest first, with the policy version that decided it. This is the audit trail.
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={onRefresh}>
            <RefreshCwIcon /> Refresh
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <div className="max-h-[560px] overflow-auto rounded-lg border">
          <Table className="min-w-[760px]">
            <TableHeader className="sticky top-0 z-10 bg-card">
              <TableRow>
                <TableHead>Time (UTC)</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead className="text-right">× usual</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Signals</TableHead>
                <TableHead>Policy</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {decisions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="h-28 text-center text-muted-foreground">
                    No decisions yet. Score a payment and it will be logged here.
                  </TableCell>
                </TableRow>
              )}
              <AnimatePresence initial={false}>
                {decisions.map((d) => (
                  <motion.tr
                    key={d.timestamp + d.policy_version}
                    layout
                    initial={{ opacity: 0, backgroundColor: "color-mix(in oklch, var(--primary) 12%, transparent)" }}
                    animate={{ opacity: 1, backgroundColor: "rgba(0,0,0,0)" }}
                    transition={{ duration: 1.2 }}
                    className="border-b transition-colors hover:bg-muted/50"
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground">{d.timestamp.replace("T", " ").slice(0, 19)}</TableCell>
                    <TableCell className="text-right font-mono tabular">₹{inr(d.inputs.amount)}</TableCell>
                    <TableCell className="text-right font-mono tabular text-muted-foreground">
                      {inr(d.inputs.amount / d.inputs.median, 1)}
                    </TableCell>
                    <TableCell className="text-right font-mono font-semibold tabular">{d.score}</TableCell>
                    <TableCell><TierBadge tier={d.tier} /></TableCell>
                    <TableCell className="max-w-[320px] text-xs whitespace-normal text-muted-foreground">
                      {d.breakdown.map((b) => `${SIGNAL_LABEL[b.signal] ?? b.signal} +${b.points}`).join(" · ") || "None"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{d.policy_version}</TableCell>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}
