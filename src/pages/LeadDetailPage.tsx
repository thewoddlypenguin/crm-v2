import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import type { Lead, Activity, LeadStatus } from "../types";
import { STATUSES, STATUS_LABELS, SEGMENTS, CONTACT_PATHS, SEGMENT_LABELS } from "../types";
import * as api from "../api";
import { PriorityBadge, StatusBadge, ScoreBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { formatDistanceToNow, format } from "date-fns";
import {
  Trash2,
  Save,
  Mail,
  Phone,
  Globe,
  Linkedin,
  MapPin,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  MessageSquare,
} from "lucide-react";

const SCORE_FIELDS = [
  { key: "offer_clarity_score", label: "Offer Clarity" },
  { key: "bottleneck_evidence_score", label: "Bottleneck Evidence" },
  { key: "buying_signal_score", label: "Buying Signal" },
  { key: "decision_maker_access_score", label: "Decision Maker Access" },
  { key: "contactability_score", label: "Contactability" },
  { key: "strategic_fit_score", label: "Strategic Fit" },
];

const QUICK_ACTIONS: { status: LeadStatus; label: string; variant: "default" | "outline" | "secondary" | "destructive" }[] = [
  { status: "CONTACTED", label: "Mark Contacted", variant: "outline" },
  { status: "FOLLOW_UP_1", label: "Follow-up 1", variant: "outline" },
  { status: "FOLLOW_UP_2", label: "Follow-up 2", variant: "outline" },
  { status: "REPLIED", label: "Mark Replied", variant: "outline" },
  { status: "CALL_BOOKED", label: "Call Booked", variant: "secondary" },
  { status: "WON", label: "Won 🎉", variant: "default" },
  { status: "CLIENT", label: "Graduate to Client", variant: "default" },
  { status: "LOST", label: "Lost", variant: "destructive" },
];

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [noteText, setNoteText] = useState("");

  // Editable form state
  const [form, setForm] = useState<Record<string, unknown>>({});

  const fetchLead = useCallback(async () => {
    if (!id) return;
    try {
      const [leadData, actData] = await Promise.all([
        api.getLead(id),
        api.listActivities(id),
      ]);
      setLead(leadData);
      setActivities(actData);
      setForm({
        first_name: leadData.first_name || "",
        last_name: leadData.last_name || "",
        business_name: leadData.business_name || "",
        segment: leadData.segment || "",
        niche: leadData.niche || "",
        email: leadData.email || "",
        website_url: leadData.website_url || "",
        contact_path: leadData.contact_path || "",
        linkedin_url: leadData.linkedin_url || "",
        location_text: leadData.location_text || "",
        team_size_estimate: leadData.team_size_estimate || "",
        source_url: leadData.source_url || "",
        personalization_note: leadData.personalization_note || "",
        outreach_angle: leadData.outreach_angle || "",
        outcome_note: leadData.outcome_note || "",
        offer_clarity_score: leadData.offer_clarity_score,
        bottleneck_evidence_score: leadData.bottleneck_evidence_score,
        buying_signal_score: leadData.buying_signal_score,
        decision_maker_access_score: leadData.decision_maker_access_score,
        contactability_score: leadData.contactability_score,
        strategic_fit_score: leadData.strategic_fit_score,
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchLead();
  }, [fetchLead]);

  const set = (field: string, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (!id) return;
    setSaving(true);
    setError("");
    try {
      const data: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(form)) {
        if (v !== "" && v !== null && v !== undefined) {
          data[k] = v;
        } else {
          data[k] = null;
        }
      }
      // Convert team_size_estimate to int
      if (data.team_size_estimate) data.team_size_estimate = parseInt(String(data.team_size_estimate));
      const updated = await api.updateLead(id, data);
      setLead(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (status: LeadStatus) => {
    if (!id) return;
    try {
      const updated = await api.changeStatus(id, status);
      setLead(updated);
      const actData = await api.listActivities(id);
      setActivities(actData);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddNote = async () => {
    if (!id || !noteText.trim()) return;
    try {
      await api.createActivity(id, { activity_type: "NOTE", body: noteText.trim() });
      setNoteText("");
      const actData = await api.listActivities(id);
      setActivities(actData);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async () => {
    if (!id || !confirm("Delete this lead? This cannot be undone.")) return;
    try {
      await api.deleteLead(id);
      navigate("/leads");
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="text-muted-foreground">Loading lead...</div>;
  if (!lead) return <div className="text-destructive">Lead not found</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {error && (
        <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">{lead.full_name || "Unnamed Lead"}</h2>
          {lead.business_name && <p className="text-muted-foreground">{lead.business_name}</p>}
          <div className="flex items-center gap-2 mt-2">
            <StatusBadge status={lead.status} />
            <PriorityBadge tier={lead.priority_tier} />
            <ScoreBadge score={lead.total_score} />
            <span className="text-xs text-muted-foreground">/12</span>
          </div>
        </div>
        <Button variant="destructive" size="sm" onClick={handleDelete}>
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {QUICK_ACTIONS.map((action) => (
              <Button
                key={action.status}
                variant={action.variant}
                size="sm"
                onClick={() => handleStatusChange(action.status)}
                disabled={lead.status === action.status}
              >
                {action.label}
              </Button>
            ))}
          </div>
          {lead.next_follow_up_at && (
            <p className={`text-sm mt-3 ${new Date(lead.next_follow_up_at) < new Date() ? "text-red-500 font-medium" : "text-muted-foreground"}`}>
              Next follow-up: {format(new Date(lead.next_follow_up_at), "MMM d, yyyy 'at' h:mm a")}
              {new Date(lead.next_follow_up_at) < new Date() && " (OVERDUE)"}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Lead Details */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Contact Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">First Name</Label>
                  <Input value={String(form.first_name || "")} onChange={(e) => set("first_name", e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Last Name</Label>
                  <Input value={String(form.last_name || "")} onChange={(e) => set("last_name", e.target.value)} />
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Business Name</Label>
                <Input value={String(form.business_name || "")} onChange={(e) => set("business_name", e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Email</Label>
                  <Input type="email" value={String(form.email || "")} onChange={(e) => set("email", e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Segment</Label>
                  <Select value={String(form.segment || "")} onValueChange={(v) => set("segment", v || null)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_none">None</SelectItem>
                      {SEGMENTS.map((s) => (
                        <SelectItem key={s} value={s}>{SEGMENT_LABELS[s]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Niche</Label>
                <Input value={String(form.niche || "")} onChange={(e) => set("niche", e.target.value)} />
              </div>

              <button
                type="button"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                onClick={() => setShowAdvanced(!showAdvanced)}
              >
                {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                Advanced fields
              </button>

              {showAdvanced && (
                <div className="space-y-3 border-t border-border pt-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Website</Label>
                      <Input value={String(form.website_url || "")} onChange={(e) => set("website_url", e.target.value)} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">LinkedIn</Label>
                      <Input value={String(form.linkedin_url || "")} onChange={(e) => set("linkedin_url", e.target.value)} />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Contact Path</Label>
                      <Select value={String(form.contact_path || "")} onValueChange={(v) => set("contact_path", v || null)}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="_none">None</SelectItem>
                          {CONTACT_PATHS.map((c) => (
                            <SelectItem key={c} value={c}>{c}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Team Size</Label>
                      <Input type="number" value={String(form.team_size_estimate || "")} onChange={(e) => set("team_size_estimate", e.target.value)} />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Location</Label>
                    <Input value={String(form.location_text || "")} onChange={(e) => set("location_text", e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Source URL</Label>
                    <Input value={String(form.source_url || "")} onChange={(e) => set("source_url", e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Personalization Note</Label>
                    <Textarea value={String(form.personalization_note || "")} onChange={(e) => set("personalization_note", e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Outreach Angle</Label>
                    <Textarea value={String(form.outreach_angle || "")} onChange={(e) => set("outreach_angle", e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Outcome Note</Label>
                    <Textarea value={String(form.outcome_note || "")} onChange={(e) => set("outcome_note", e.target.value)} />
                  </div>
                </div>
              )}

              <Button onClick={handleSave} disabled={saving} size="sm" className="gap-2">
                <Save className="h-3 w-3" />
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right: Scoring + Timeline */}
        <div className="space-y-6">
          {/* Scoring */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Scoring</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-lg font-bold text-foreground">{lead.total_score}</span>
                  <span className="text-muted-foreground">/12</span>
                </div>
                <PriorityBadge tier={lead.priority_tier} />
              </div>
              {SCORE_FIELDS.map((sf) => (
                <div key={sf.key} className="flex items-center justify-between gap-3">
                  <Label className="text-xs flex-1">{sf.label}</Label>
                  <div className="flex gap-1">
                    {[0, 1, 2].map((val) => (
                      <button
                        key={val}
                        type="button"
                        className={`h-7 w-7 rounded text-xs font-medium transition-colors ${
                          Number(form[sf.key]) === val
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:bg-accent"
                        }`}
                        onClick={() => {
                          setForm((prev) => ({ ...prev, [sf.key]: val }));
                          // Auto-save scoring
                          api.updateLead(id!, { [sf.key]: val }).then((updated) => setLead(updated));
                        }}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Add Note */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Add Note
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add a note..."
                  className="min-h-[60px]"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      handleAddNote();
                    }
                  }}
                />
              </div>
              <Button size="sm" className="mt-2" onClick={handleAddNote} disabled={!noteText.trim()}>
                Add Note
              </Button>
            </CardContent>
          </Card>

          {/* Activity Timeline */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {activities.length === 0 ? (
                <p className="text-sm text-muted-foreground">No activity yet</p>
              ) : (
                <div className="space-y-3">
                  {activities.map((act) => (
                    <div key={act.id} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div className={`h-2 w-2 rounded-full mt-2 ${
                          act.activity_type === "STATUS_CHANGE" ? "bg-blue-500" :
                          act.activity_type === "NOTE" ? "bg-gray-400" :
                          "bg-green-500"
                        }`} />
                        <div className="w-px flex-1 bg-border" />
                      </div>
                      <div className="flex-1 pb-3">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px]">{act.activity_type}</Badge>
                          {act.occurred_at && (
                            <span className="text-[10px] text-muted-foreground">
                              {formatDistanceToNow(new Date(act.occurred_at), { addSuffix: true })}
                            </span>
                          )}
                        </div>
                        {act.body && <p className="text-sm text-foreground mt-1">{act.body}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
