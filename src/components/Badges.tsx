import type { PriorityTier, LeadStatus } from "../types";
import { STATUS_LABELS } from "../types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const tierStyles: Record<PriorityTier, string> = {
  A: "bg-green-500/15 text-green-600 border-green-500/30",
  B: "bg-yellow-500/15 text-yellow-600 border-yellow-500/30",
  C: "bg-muted text-muted-foreground border-border",
};

const statusStyles: Record<string, string> = {
  NEW: "bg-blue-500/15 text-blue-600 border-blue-500/30",
  SCORED: "bg-indigo-500/15 text-indigo-600 border-indigo-500/30",
  READY_TO_CONTACT: "bg-cyan-500/15 text-cyan-600 border-cyan-500/30",
  CONTACTED: "bg-purple-500/15 text-purple-600 border-purple-500/30",
  FOLLOW_UP_1: "bg-orange-500/15 text-orange-600 border-orange-500/30",
  FOLLOW_UP_2: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  REPLIED: "bg-green-500/15 text-green-600 border-green-500/30",
  CALL_BOOKED: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30",
  WON: "bg-green-600/20 text-green-700 border-green-600/40",
  CLIENT: "bg-blue-600/20 text-blue-700 border-blue-600/40",
  LOST: "bg-red-500/15 text-red-600 border-red-500/30",
  NURTURE: "bg-muted text-muted-foreground border-border",
};

export function PriorityBadge({ tier }: { tier: PriorityTier }) {
  return (
    <Badge variant="outline" className={cn("text-xs font-medium", tierStyles[tier])}>
      {tier}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: LeadStatus }) {
  return (
    <Badge variant="outline" className={cn("text-xs font-medium", statusStyles[status] || statusStyles.NEW)}>
      {STATUS_LABELS[status]}
    </Badge>
  );
}

export function ScoreBadge({ score }: { score: number }) {
  const color = score >= 10 ? "text-green-600" : score >= 7 ? "text-yellow-600" : "text-muted-foreground";
  return <span className={cn("text-sm font-semibold", color)}>{score}</span>;
}
