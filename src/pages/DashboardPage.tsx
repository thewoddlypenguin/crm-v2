import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import type { DashboardData } from "../types";
import * as api from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriorityBadge, StatusBadge } from "@/components/Badges";
import {
  MailCheck,
  MessageSquare,
  PhoneIncoming,
  Trophy,
  AlertCircle,
  Clock,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDashboard()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-muted-foreground">Loading dashboard...</div>;
  if (!data) return <div className="text-destructive">Failed to load dashboard</div>;

  const kpis = [
    { label: "Contacted This Week", value: data.leads_contacted_week, icon: MailCheck, color: "text-blue-500" },
    { label: "Replies This Week", value: data.replies_week, icon: MessageSquare, color: "text-green-500" },
    { label: "Calls Booked This Week", value: data.calls_booked_week, icon: PhoneIncoming, color: "text-purple-500" },
    { label: "Wins This Month", value: data.wins_month, icon: Trophy, color: "text-emerald-500" },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{kpi.label}</p>
                  <p className="text-3xl font-bold text-foreground">{kpi.value}</p>
                </div>
                <kpi.icon className={`h-8 w-8 ${kpi.color} opacity-80`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Follow-ups Due Today */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="h-5 w-5 text-blue-500" />
            Follow-ups Due Today
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.follow_ups_due_today.length === 0 ? (
            <p className="text-sm text-muted-foreground">No follow-ups due today</p>
          ) : (
            <div className="space-y-2">
              {data.follow_ups_due_today.map((lead) => (
                <Link
                  key={lead.id}
                  to={`/leads/${lead.id}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-blue-500/5 border border-blue-500/20 hover:bg-blue-500/10 transition-colors"
                >
                  <div>
                    <span className="font-medium text-foreground">{lead.full_name || lead.business_name}</span>
                    {lead.business_name && lead.full_name && (
                      <span className="text-muted-foreground ml-2 text-sm">{lead.business_name}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={lead.status} />
                    <PriorityBadge tier={lead.priority_tier} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Overdue Follow-ups */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertCircle className="h-5 w-5 text-red-500" />
            Overdue Follow-ups
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.overdue_follow_ups.length === 0 ? (
            <p className="text-sm text-muted-foreground">No overdue follow-ups</p>
          ) : (
            <div className="space-y-2">
              {data.overdue_follow_ups.map((lead) => (
                <Link
                  key={lead.id}
                  to={`/leads/${lead.id}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-red-500/5 border border-red-500/20 hover:bg-red-500/10 transition-colors"
                >
                  <div>
                    <span className="font-medium text-foreground">{lead.full_name || lead.business_name}</span>
                    {lead.business_name && lead.full_name && (
                      <span className="text-muted-foreground ml-2 text-sm">{lead.business_name}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {lead.next_follow_up_at && (
                      <span className="text-xs text-red-500">
                        {formatDistanceToNow(new Date(lead.next_follow_up_at), { addSuffix: true })}
                      </span>
                    )}
                    <StatusBadge status={lead.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
