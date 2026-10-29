import { cn } from "@/lib/utils"
import type { Tier } from "@/lib/api"
import { TIER } from "@/lib/domain"

export function TierBadge({ tier, label, className }: { tier: Tier; label?: string; className?: string }) {
  const color = TIER[tier].color
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        className
      )}
      style={{ color, backgroundColor: `color-mix(in oklch, ${color} 14%, transparent)` }}
    >
      <span className="size-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label ?? TIER[tier].short}
    </span>
  )
}
