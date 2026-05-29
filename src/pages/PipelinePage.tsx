import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { PipelineData, Lead, LeadStatus } from "../types";
import { STATUSES, STATUS_LABELS } from "../types";
import * as api from "../api";
import { PriorityBadge, StatusBadge, ScoreBadge } from "@/components/Badges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow } from "date-fns";

const COLUMN_COLORS: Record<string, string> = {
  NEW: "border-t-blue-500",
  SCORED: "border-t-indigo-500",
  READY_TO_CONTACT: "border-t-cyan-500",
  CONTACTED: "border-t-purple-500",
  FOLLOW_UP_1: "border-t-orange-500",
  FOLLOW_UP_2: "border-t-amber-500",
  REPLIED: "border-t-green-500",
  CALL_BOOKED: "border-t-emerald-500",
  WON: "border-t-green-600",
  CLIENT: "border-t-blue-600",
  LOST: "border-t-red-500",
  NURTURE: "border-t-gray-400",
};

export default function PipelinePage() {
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [moving, setMoving] = useState<string | null>(null);

  useEffect(() => {
    api.getPipeline()
      .then(setPipeline)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleMove = async (leadId: string, newStatus: LeadStatus) => {
    setMoving(leadId);
    try {
      await api.changeStatus(leadId, newStatus);
      const updated = await api.getPipeline();
      setPipeline(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setMoving(null);
    }
  };

  if (loading) return <div className="text-muted-foreground">Loading pipeline...</div>;
  if (!pipeline) return <div className="text-destructive">Failed to load pipeline</div>;

  return (
    <div className="overflow-x-auto">
      <div className="flex gap-4 pb-4" style={{ minWidth: STATUSES.length * 240 }}>
        {STATUSES.map((status) => {
          const leads = pipeline[status] || [];
          return (
            <div
              key={status}
              className={`flex-shrink-0 w-60 border-t-2 ${COLUMN_COLORS[status] || "border-t-gray-400"}`}
            >
              <div className="flex items-center justify-between py-2">
                <h3 className="text-sm font-medium text-foreground">{STATUS_LABELS[status]}</h3>
                <Badge variant="secondary" className="text-xs">{leads.length}</Badge>
              </div>
              <div className="space-y-2">
                {leads.length === 0 ? (
                  <div className="text-xs text-muted-foreground text-center py-4 border border-dashed border-border rounded-lg">
                    No leads
                  </div>
                ) : (
                  leads.map((lead) => (
                    <Card key={lead.id} className="group">
                      <CardContent className="p-3 space-y-2">
                        <Link
                          to={`/leads/${lead.id}`}
                          className="text-sm font-medium text-foreground hover:underline block"
                        >
                          {lead.full_name || "Unnamed"}
                        </Link>
                        {lead.business_name && (
                          <p className="text-xs text-muted-foreground">{lead.business_name}</p>
                        )}
                        <div className="flex items-center gap-2">
                          <PriorityBadge tier={lead.priority_tier} />
                          <ScoreBadge score={lead.total_score} />
                        </div>
                        {lead.next_follow_up_at && (
                          <p className={`text-xs ${new Date(lead.next_follow_up_at) < new Date() ? "text-red-500 font-medium" : "text-muted-foreground"}`}>
                            FU: {formatDistanceToNow(new Date(lead.next_follow_up_at), { addSuffix: true })}
                          </p>
                        )}
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                          <Select
                            onValueChange={(v) => handleMove(lead.id, v as LeadStatus)}
                            disabled={moving === lead.id}
                          >
                            <SelectTrigger className="h-7 text-xs">
                              <SelectValue placeholder="Move to..." />
                            </SelectTrigger>
                            <SelectContent>
                              {STATUSES.filter((s) => s !== status).map((s) => (
                                <SelectItem key={s} value={s}>{STATUS_LABELS[s]}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
