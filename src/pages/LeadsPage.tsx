import { useState, useEffect, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import type { Lead, LeadStatus, PriorityTier, SegmentOption } from "../types";
import { STATUSES, STATUS_LABELS } from "../types";
import * as api from "../api";
import { PriorityBadge, StatusBadge, ScoreBadge, DncBadge } from "@/components/Badges";
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
import { Search, Plus, MoreHorizontal, Trash2, ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface SortableHeadProps {
  label: string;
  col: string;
  active: boolean;
  dir: "asc" | "desc";
  onToggle: (col: string) => void;
}

/** Clickable table header with sort state: neutral ⇅ / active ↑ asc / ↓ desc. */
function SortableHead({ label, col, active, dir, onToggle }: SortableHeadProps) {
  const Icon = !active ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <TableHead
      className={`bg-muted/50 text-xs font-semibold uppercase tracking-wide cursor-pointer select-none hover:text-foreground transition-colors ${
        active ? "text-foreground" : "text-muted-foreground"
      }`}
      onClick={() => onToggle(col)}
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <div className="flex items-center gap-1">
        {label} <Icon className="h-3 w-3" />
      </div>
    </TableHead>
  );
}

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
  const [allTags, setAllTags] = useState<string[]>([]);
  const [tagFilter, setTagFilter] = useState<string>("all");
  const [bulkTagMode, setBulkTagMode] = useState<"add" | "remove">("add");
  const [bulkTagInput, setBulkTagInput] = useState("");

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
        tag: tagFilter !== "all" ? tagFilter : undefined,
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
  }, [search, statusFilter, priorityFilter, segmentFilter, tagFilter, sortBy, sortDir, page]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  useEffect(() => {
    api
      .listSegments()
      .then(setSegments)
      .catch((err) => console.error("Failed to load segments", err));
    api
      .listLeadTags()
      .then((res) => setAllTags(res.tags))
      .catch((err) => console.error("Failed to load tags", err));
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

  const handleBulkTags = async () => {
    const tags = bulkTagInput.split(",").map((t) => t.trim()).filter(Boolean);
    if (selectedIds.size === 0 || tags.length === 0) return;
    try {
      await api.bulkTagChange(Array.from(selectedIds), tags, bulkTagMode);
      setSelectedIds(new Set());
      setBulkTagInput("");
      fetchLeads();
      api
        .listLeadTags()
        .then((res) => setAllTags(res.tags))
        .catch(() => {});
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
      <div className="flex flex-col sm:flex-row gap-3 bg-card border border-border rounded-lg px-4 py-3 shadow-sm">
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

        <Select
          value={tagFilter}
          onValueChange={(v) => {
            setTagFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Tag" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Tags</SelectItem>
            {allTags.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
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
      {["NEW", "CONTACTED", "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED", "WON", "CLIENT", "LOST"].map((s) => (
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

    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">Tags:</span>
      <Select value={bulkTagMode} onValueChange={(v) => setBulkTagMode(v as "add" | "remove")}>
        <SelectTrigger className="w-[130px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="add">Add tags</SelectItem>
          <SelectItem value="remove">Remove tags</SelectItem>
        </SelectContent>
      </Select>
      <Input
        className="w-[220px]"
        placeholder="tag1, tag2 (Enter to apply)"
        value={bulkTagInput}
        onChange={(e) => setBulkTagInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            handleBulkTags();
          }
        }}
      />
      <Button variant="default" size="sm" onClick={handleBulkTags} disabled={!bulkTagInput.trim()}>
        Apply tags
      </Button>
    </div>
  </div>
)}


      <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10 bg-muted/50">
                <Checkbox
                  checked={selectedIds.size === leads.length && leads.length > 0}
                  onCheckedChange={toggleAll}
                />
              </TableHead>
              <SortableHead label="Name" col="full_name" active={sortBy === "full_name"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <SortableHead label="Business" col="business_name" active={sortBy === "business_name"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <SortableHead label="Niche" col="niche" active={sortBy === "niche"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <SortableHead label="Segment" col="segment" active={sortBy === "segment"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <SortableHead label="Status" col="status" active={sortBy === "status"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <TableHead className="bg-muted/50 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tags</TableHead>
              <SortableHead label="Score" col="total_score" active={sortBy === "total_score"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <SortableHead label="Priority" col="priority_tier" active={sortBy === "priority_tier"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <SortableHead label="Next Follow-up" col="next_follow_up_at" active={sortBy === "next_follow_up_at"} dir={sortDir as "asc" | "desc"} onToggle={toggleSort} />
              <TableHead className="w-10 bg-muted/50" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={11} className="text-center text-muted-foreground py-8">
                  Loading...
                </TableCell>
              </TableRow>
            ) : leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={11} className="text-center text-muted-foreground py-8">
                  No leads found
                </TableCell>
              </TableRow>
            ) : (
              leads.map((lead) => (
                <TableRow
                  key={lead.id}
                  className="cursor-pointer hover:bg-muted/30 transition-colors"
                  onClick={() => {
                    window.location.href = `/leads/${lead.id}`;
                  }}
                >
                  <TableCell className="py-3" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={selectedIds.has(lead.id)}
                      onCheckedChange={() => toggleSelect(lead.id)}
                    />
                  </TableCell>

                  <TableCell className="py-3">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/leads/${lead.id}`}
                        className="font-medium text-foreground text-sm hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {lead.full_name || "—"}
                      </Link>
                      {lead.do_not_contact && <DncBadge />}
                    </div>
                  </TableCell>

                  <TableCell className="py-3 text-xs text-muted-foreground">{lead.business_name || "—"}</TableCell>

                  <TableCell className="py-3 text-xs text-muted-foreground">{lead.niche || "—"}</TableCell>

                  <TableCell className="py-3">
                    <span className="text-xs text-muted-foreground">
                      {lead.segment_label || (lead.segment ? segmentLabelMap[lead.segment] || lead.segment : "—")}
                    </span>
                  </TableCell>


                  <TableCell className="py-3">
                    <StatusBadge status={lead.status} />
                  </TableCell>

                  <TableCell className="py-3">
                    <div className="flex flex-wrap gap-1">
                      {(lead.tags || []).slice(0, 3).map((t) => (
                        <span key={t} className="inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                          {t}
                        </span>
                      ))}
                      {(lead.tags || []).length > 3 && (
                        <span className="text-[11px] text-muted-foreground">+{lead.tags!.length - 3}</span>
                      )}
                      {(!lead.tags || lead.tags.length === 0) && (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </div>
                  </TableCell>

                  <TableCell className="py-3">
                    <ScoreBadge score={lead.total_score} />
                  </TableCell>

                  <TableCell className="py-3">
                    <PriorityBadge tier={lead.priority_tier} />
                  </TableCell>

                  <TableCell className="py-3">
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

                  <TableCell className="py-3" onClick={(e) => e.stopPropagation()}>
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