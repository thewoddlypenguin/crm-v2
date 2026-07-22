import { useState, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import type { Lead, LeadStatus, PriorityTier, SegmentOption } from "../types";
import { STATUSES, STATUS_LABELS } from "../types";
import * as api from "../api";
import { PriorityBadge, StatusBadge, ScoreBadge } from "@/components/Badges";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Checkbox } from "@/components/ui/checkbox";
import { Search, Plus, MoreHorizontal, Trash2, ArrowUpDown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [segments, setSegments] = useState<SegmentOption[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [segmentFilter, setSegmentFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState("total_score");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkSegmentId, setBulkSegmentId] = useState<string>("");

  const segmentLabelMap = useMemo(
    () =>
      Object.fromEntries(
        segments.map((s) => [s.key.toUpperCase(), s.label])
      ) as Record<string, string>,
    [segments]
  );

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listLeads({
        search: search || undefined,
        status: statusFilter !== "all" ? (statusFilter as LeadStatus) : undefined,
        priority: priorityFilter !== "all" ? (priorityFilter as PriorityTier) : undefined,
        segment_id: segmentFilter !== "all" ? segmentFilter : undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        page_size: 50,
      });
      setLeads(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, priorityFilter, segmentFilter, sortBy, sortDir, page]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  useEffect(() => {
    api
      .listSegments()
      .then(setSegments)
      .catch((err) => console.error("Failed to load segments", err));
  }, []);

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(sortDir === "desc" ? "asc" : "desc");
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const toggleAll = () => {
    if (selectedIds.size === leads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(leads.map((l) => l.id)));
    }
  };

  const handleBulkStatus = async (status: LeadStatus) => {
    if (selectedIds.size === 0) return;
    try {
      await api.bulkStatusChange(Array.from(selectedIds), status);
      setSelectedIds(new Set());
      fetchLeads();
    } catch (err) {
      console.error(err);
    }
  };
  const handleBulkSegment = async () => {
    if (selectedIds.size === 0 || !bulkSegmentId) return;
    try {
      await api.bulkSegmentChange(Array.from(selectedIds), bulkSegmentId);
      setSelectedIds(new Set());
      setBulkSegmentId("");
      fetchLeads();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this lead? This cannot be undone.")) return;
    try {
      await api.deleteLead(id);
      fetchLeads();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search name, business, email..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-9"
          />
        </div>

        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Status" />
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

        <Select
          value={priorityFilter}
          onValueChange={(v) => {
            setPriorityFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Priorities</SelectItem>
            <SelectItem value="A">A (High)</SelectItem>
            <SelectItem value="B">B (Medium)</SelectItem>
            <SelectItem value="C">C (Low)</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={segmentFilter}
          onValueChange={(v) => {
            setSegmentFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Segment" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Segments</SelectItem>
            {segments.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.label}
              </SelectItem>
            ))}

          </SelectContent>
        </Select>

        <Link to="/leads/new">
          <Button className="gap-2">
            <Plus className="h-4 w-4" />
            New Lead
          </Button>
        </Link>
      </div>

      {selectedIds.size > 0 && (
  <div className="flex flex-col gap-3 p-3 bg-muted rounded-lg">
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">{selectedIds.size} selected</span>
      <span className="text-muted-foreground">→</span>
      {["CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON", "CLIENT", "LOST"].map((s) => (
        <Button key={s} variant="outline" size="sm" onClick={() => handleBulkStatus(s as LeadStatus)}>
          {STATUS_LABELS[s as LeadStatus]}
        </Button>
      ))}
    </div>

    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">Change segment:</span>
      <Select value={bulkSegmentId} onValueChange={setBulkSegmentId}>
        <SelectTrigger className="w-[220px]">
          <SelectValue placeholder="Select segment" />
        </SelectTrigger>
        <SelectContent>
          {segments.map((s) => (
            <SelectItem key={s.id} value={s.id}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        variant="default"
        size="sm"
        onClick={handleBulkSegment}
        disabled={!bulkSegmentId}
      >
        Apply segment
      </Button>
    </div>
  </div>
)}


      <div className="border border-border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={selectedIds.size === leads.length && leads.length > 0}
                  onCheckedChange={toggleAll}
                />
              </TableHead>
              <TableHead className="cursor-pointer" onClick={() => toggleSort("full_name")}>
                Name
              </TableHead>
              <TableHead>Business</TableHead>
              <TableHead>Segment</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="cursor-pointer" onClick={() => toggleSort("total_score")}>
                <div className="flex items-center gap-1">
                  Score <ArrowUpDown className="h-3 w-3" />
                </div>
              </TableHead>
              <TableHead>Priority</TableHead>
              <TableHead className="cursor-pointer" onClick={() => toggleSort("next_follow_up_at")}>
                <div className="flex items-center gap-1">
                  Next Follow-up <ArrowUpDown className="h-3 w-3" />
                </div>
              </TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-muted-foreground py-8">
                  Loading...
                </TableCell>
              </TableRow>
            ) : leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-muted-foreground py-8">
                  No leads found
                </TableCell>
              </TableRow>
            ) : (
              leads.map((lead) => (
                <TableRow
                  key={lead.id}
                  className="cursor-pointer"
                  onClick={() => {
                    window.location.href = `/leads/${lead.id}`;
                  }}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={selectedIds.has(lead.id)}
                      onCheckedChange={() => toggleSelect(lead.id)}
                    />
                  </TableCell>

                  <TableCell className="font-medium">
                    <Link
                      to={`/leads/${lead.id}`}
                      className="hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {lead.full_name || "—"}
                    </Link>
                  </TableCell>

                  <TableCell className="text-muted-foreground">{lead.business_name || "—"}</TableCell>

                  <TableCell>
                    <span className="text-xs text-muted-foreground">
                      {lead.segment_label || (lead.segment ? segmentLabelMap[lead.segment] || lead.segment : "—")}
                    </span>
                  </TableCell>


                  <TableCell>
                    <StatusBadge status={lead.status} />
                  </TableCell>

                  <TableCell>
                    <ScoreBadge score={lead.total_score} />
                  </TableCell>

                  <TableCell>
                    <PriorityBadge tier={lead.priority_tier} />
                  </TableCell>

                  <TableCell>
                    {lead.next_follow_up_at ? (
                      <span
                        className={`text-xs ${
                          new Date(lead.next_follow_up_at) < new Date()
                            ? "text-red-500 font-medium"
                            : "text-muted-foreground"
                        }`}
                      >
                        {formatDistanceToNow(new Date(lead.next_follow_up_at), { addSuffix: true })}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>

                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link to={`/leads/${lead.id}`}>View</Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => handleDelete(lead.id)}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {total > 50 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Showing {(page - 1) * 50 + 1}–{Math.min(page * 50, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Button variant="outline" size="sm" disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}