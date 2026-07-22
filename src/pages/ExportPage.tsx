import { useEffect, useState } from "react";
import type { LeadStatus, PriorityTier, SegmentOption, SegmentValue } from "../types";
import { STATUSES, STATUS_LABELS } from "../types";
import * as api from "../api";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Download } from "lucide-react";

export default function ExportPage() {
  const [segments, setSegments] = useState<SegmentOption[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [segmentFilter, setSegmentFilter] = useState<string>("all");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api
      .listSegments()
      .then(setSegments)
      .catch((err) => console.error("Failed to load segments", err));
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await api.downloadCSV({
        status: statusFilter !== "all" ? (statusFilter as LeadStatus) : undefined,
        priority: priorityFilter !== "all" ? (priorityFilter as PriorityTier) : undefined,
        segment: segmentFilter !== "all" ? (segmentFilter as SegmentValue) : undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "leads_export.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Export Leads</CardTitle>
          <CardDescription>Download your leads as a CSV file with optional filters</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Status</label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  {STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Priority</label>
              <Select value={priorityFilter} onValueChange={setPriorityFilter}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Priorities</SelectItem>
                  <SelectItem value="A">A (High)</SelectItem>
                  <SelectItem value="B">B (Medium)</SelectItem>
                  <SelectItem value="C">C (Low)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Segment</label>
              <Select value={segmentFilter} onValueChange={setSegmentFilter}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Segments</SelectItem>
                  {segments.map((s) => (
                    <SelectItem key={s.id} value={s.key.toUpperCase()}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button onClick={handleExport} disabled={exporting} className="gap-2">
            <Download className="h-4 w-4" />
            {exporting ? "Exporting..." : "Export CSV"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}