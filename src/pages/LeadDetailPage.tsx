import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CONTACT_PATHS, STATUS_LABELS } from "../types";
import type { Activity, ContactPath, EmailTemplate, Lead, SegmentOption } from "../types";
import * as api from "../api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [lead, setLead] = useState<Lead | null>(null);
  const [segments, setSegments] = useState<SegmentOption[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [notes, setNotes] = useState<Activity[]>([]);
  const [noteText, setNoteText] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editNoteText, setEditNoteText] = useState("");

  // All activities (for history stream)
  const [activities, setActivities] = useState<Activity[]>([]);

  // Email compose state
  const [emailSubject, setEmailSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [emailSending, setEmailSending] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailSuccess, setEmailSuccess] = useState<string | null>(null); // message string or null

  // Email templates
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);

  // Tab navigation for view mode
  type ViewTab = "contact" | "business" | "notes" | "email" | "history";
  const [activeTab, setActiveTab] = useState<ViewTab>("contact");

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    business_name: "",
    segment_id: "",
    niche: "",
    email: "",
    phone: "",
    website_url: "",
    contact_path: "" as ContactPath | "",
    linkedin_url: "",
    location_text: "",
    team_size_estimate: "",
    source_url: "",
    personalization_note: "",
    outreach_angle: "",
    do_not_contact: false,
  });

  const fillForm = (data: Lead) => {
    setForm({
      first_name: data.first_name || "",
      last_name: data.last_name || "",
      business_name: data.business_name || "",
      segment_id: data.segment_id || "",
      niche: data.niche || "",
      email: data.email || "",
      phone: data.phone || "",
      website_url: data.website_url || "",
      contact_path: (data.contact_path || "") as ContactPath | "",
      linkedin_url: data.linkedin_url || "",
      location_text: data.location_text || "",
      team_size_estimate:
        data.team_size_estimate != null ? String(data.team_size_estimate) : "",
      source_url: data.source_url || "",
      personalization_note: data.personalization_note || "",
      outreach_angle: data.outreach_angle || "",
      do_not_contact: data.do_not_contact ?? false,
    });
  };

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!id) {
        setError("Missing lead ID");
        setInitialLoading(false);
        return;
      }

      try {
        const [leadData, segmentOptions, activityData, templateData] = await Promise.all([
          api.getLead(id),
          api.listSegments(),
          api.listActivities(id),
          api.listEmailTemplates(),
        ]);

        if (cancelled) return;

        setTemplates(templateData);
        setActivities(activityData);
        setLead(leadData);
        setSegments(segmentOptions);
        setNotes(activityData.filter((a) => a.activity_type === "NOTE"));
        fillForm(leadData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load lead");
        }
      } finally {
        if (!cancelled) setInitialLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const set = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleEdit = () => {
    if (lead) fillForm(lead);
    setError("");
    setEditing(true);
  };

  const handleCancelEdit = () => {
    if (lead) fillForm(lead);
    setError("");
    setEditing(false);
    setShowAdvanced(false);
  };

  const refreshActivities = async () => {
    if (!id) return;
    const activityData = await api.listActivities(id);
    setNotes(activityData.filter((a) => a.activity_type === "NOTE"));
    setActivities(activityData);
  };

  const handleAddNote = async () => {
    if (!id || !noteText.trim()) return;
    try {
      await api.createActivity(id, { activity_type: "NOTE", body: noteText.trim() });
      setNoteText("");
      await refreshActivities();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveNote = async (noteId: string) => {
    if (!id || !editNoteText.trim()) return;
    try {
      await api.updateActivity(id, noteId, editNoteText.trim());
      setEditingNoteId(null);
      setEditNoteText("");
      await refreshActivities();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    if (!id || !confirm("Delete this note?")) return;
    try {
      await api.deleteActivity(id, noteId);
      await refreshActivities();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSendEmail = async () => {
    if (!id || !emailSubject.trim() || !emailBody.trim()) return;
    setEmailSending(true);
    setEmailError(null);
    setEmailSuccess(null);
    try {
      const result = await api.sendLeadEmail(id, { subject: emailSubject.trim(), body: emailBody.trim() });
      setEmailSubject("");
      setEmailBody("");
      setEmailSuccess(result.simulated ? "Simulated (test mode) — not delivered." : "Email sent successfully.");
      await refreshActivities();
    } catch (err: unknown) {
      setEmailError(err instanceof Error ? err.message : "Failed to send email");
    } finally {
      setEmailSending(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;

    setError("");
    setSaving(true);

    try {
      const data: Record<string, unknown> = {
        first_name: form.first_name || null,
        last_name: form.last_name || null,
        business_name: form.business_name || null,
        segment_id: form.segment_id || null,
        niche: form.niche || null,
        email: form.email || null,
        phone: form.phone || null,
        website_url: form.website_url || null,
        contact_path: form.contact_path || null,
        linkedin_url: form.linkedin_url || null,
        location_text: form.location_text || null,
        team_size_estimate: form.team_size_estimate
          ? parseInt(form.team_size_estimate, 10)
          : null,
        source_url: form.source_url || null,
        personalization_note: form.personalization_note || null,
        outreach_angle: form.outreach_angle || null,
        do_not_contact: form.do_not_contact,
      };

      const updated = await api.updateLead(id, data);
      setLead(updated);
      fillForm(updated);
      setEditing(false);
      setShowAdvanced(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update lead");
    } finally {
      setSaving(false);
    }
  };

  const displayValue = (value?: string | number | null) =>
    value !== null && value !== undefined && value !== "" ? String(value) : "Not provided";

  const detailRow = (label: string, value?: string | number | null) => (
    <div className="space-y-1 rounded-lg border bg-background p-4">
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </div>
      <div className="text-sm leading-6 text-foreground break-words">
        {displayValue(value)}
      </div>
    </div>
  );

  const scoreCard = (label: string, value?: string | number | null) => (
    <div className="rounded-xl border bg-muted/30 p-4">
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold">
        {value !== null && value !== undefined && value !== "" ? value : "—"}
      </div>
    </div>
  );

  const badgeClass = (tone: "default" | "success" | "warning" | "muted" = "default") => {
    const base =
      "inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium";
    if (tone === "success") {
      return `${base} border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300`;
    }
    if (tone === "warning") {
      return `${base} border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300`;
    }
    if (tone === "muted") {
      return `${base} border-border bg-muted text-muted-foreground`;
    }
    return `${base} border-primary/20 bg-primary/10 text-primary`;
  };

  const getPriorityTone = (priority?: string | null) => {
    if (priority === "A") return "success";
    if (priority === "B") return "default";
    return "muted";
  };

  const statusLabel = lead ? STATUS_LABELS[lead.status] || lead.status : "";
  const segmentLabel = lead?.segment_label || lead?.segment || "No segment";

  if (initialLoading) {
    return <div className="text-muted-foreground">Loading lead...</div>;
  }

  if (!lead) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardContent className="py-6">
            <div className="text-sm text-destructive">{error || "Lead not found."}</div>
            <div className="pt-4">
              <Button variant="outline" onClick={() => navigate("/leads")}>
                Back to Leads
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Activity type labels for the history stream
  const ACTIVITY_LABELS: Record<string, string> = {
    NOTE: "Note",
    STATUS_CHANGE: "Status Change",
    OUTREACH_SENT: "Email Sent",
    FOLLOW_UP_SENT: "Follow-up Sent",
    REPLY_RECEIVED: "Reply Received",
    CALL_BOOKED: "Call Booked",
    OTHER: "Other",
  };

  // ── Tab state ──
  const TABS: { id: ViewTab; label: string }[] = [
    { id: "contact", label: "Contact Details" },
    { id: "business", label: "Business Profile" },
    { id: "notes", label: "Notes & Context" },
    { id: "email", label: "Email" },
    { id: "history", label: "Activity History" },
  ];

  if (!editing) {
    return (
      <div className="mx-auto max-w-6xl">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive mb-6">
            {error}
          </div>
        )}

        {/* ── Hero Card ── */}
        <Card className="overflow-hidden border-border/70 mb-6">
          <CardHeader className="gap-6 bg-muted/30 pb-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div className="space-y-3">
                <div className="space-y-1">
                  <CardTitle className="text-2xl md:text-3xl">
                    {lead.full_name || lead.business_name || "Lead Detail"}
                  </CardTitle>
                  <div className="text-sm text-muted-foreground">
                    {lead.business_name || "No business name"}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className={badgeClass("default")}>{statusLabel}</span>
                  <span className={badgeClass(getPriorityTone(lead.priority_tier) as "default" | "success" | "warning" | "muted")}>
                    Priority {displayValue(lead.priority_tier)}
                  </span>
                  <span className={badgeClass("muted")}>{segmentLabel}</span>
                  {lead.do_not_contact && (
                    <span className="inline-flex items-center rounded-full border border-destructive/40 bg-destructive/10 px-3 py-1 text-xs font-medium text-destructive">
                      DNC
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => navigate("/leads")}>
                  Back
                </Button>
                <Button onClick={handleEdit}>Edit</Button>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 border-t pt-4 text-sm text-muted-foreground md:grid-cols-3">
              <div>
                <span className="font-medium text-foreground">Created:</span>{" "}
                {displayValue(lead.created_at)}
              </div>
              <div>
                <span className="font-medium text-foreground">Last contacted:</span>{" "}
                {displayValue(lead.last_contacted_at)}
              </div>
              <div>
                <span className="font-medium text-foreground">Next follow up:</span>{" "}
                {displayValue(lead.next_follow_up_at)}
              </div>
            </div>
          </CardHeader>
        </Card>

        {/* ── Tab Navigation ── */}
        <div className="flex gap-1 border-b border-border mb-6 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Tab: Contact Details ── */}
        {activeTab === "contact" && (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Contact Information</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {detailRow("First Name", lead.first_name)}
                  {detailRow("Last Name", lead.last_name)}
                  {detailRow("Email", lead.email)}
                  {detailRow("Phone", lead.phone)}
                  {detailRow("Contact Path", lead.contact_path)}
                  {detailRow("Website", lead.website_url)}
                  {detailRow("LinkedIn", lead.linkedin_url)}
                  {detailRow("Location", lead.location_text)}
                  {detailRow("Follow Up Count", lead.follow_up_count)}
                </CardContent>
              </Card>
            </div>
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Lead Scores</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-3">
                  {scoreCard("Offer Clarity", lead.offer_clarity_score)}
                  {scoreCard("Bottleneck Evidence", lead.bottleneck_evidence_score)}
                  {scoreCard("Buying Signal", lead.buying_signal_score)}
                  {scoreCard("Decision Maker Access", lead.decision_maker_access_score)}
                  {scoreCard("Contactability", lead.contactability_score)}
                  {scoreCard("Strategic Fit", lead.strategic_fit_score)}
                </CardContent>
              </Card>
              <Card className="border-primary/20 bg-primary/5">
                <CardHeader>
                  <CardTitle className="text-base">Total Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-4xl font-semibold tracking-tight">
                    {lead.total_score ?? "—"}
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    Aggregate score across the six qualification categories.
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Outreach Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Do Not Contact</span>
                      <span className={`text-sm font-medium ${lead.do_not_contact ? "text-destructive" : "text-muted-foreground"}`}>
                        {lead.do_not_contact ? "⛔ Blocked" : "Allowed"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Last Contacted</span>
                      <span className="text-sm font-medium">{displayValue(lead.last_contacted_at)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Next Follow-up</span>
                      <span className="text-sm font-medium">{displayValue(lead.next_follow_up_at)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ── Tab: Business Profile ── */}
        {activeTab === "business" && (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Business Information</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {detailRow("Business Name", lead.business_name)}
                  {detailRow("Segment", segmentLabel)}
                  {detailRow("Niche", lead.niche)}
                  {detailRow("Team Size", lead.team_size_estimate)}
                  {detailRow("Source URL", lead.source_url)}
                  {detailRow("Priority Tier", lead.priority_tier)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Context & Strategy</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-4">
                  {detailRow("Personalization Note", lead.personalization_note)}
                  {detailRow("Outreach Angle", lead.outreach_angle)}
                  {detailRow("Outcome Note", lead.outcome_note)}
                </CardContent>
              </Card>
            </div>
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Location</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-sm">{displayValue(lead.location_text)}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Links</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground mb-1">
                      Website
                    </div>
                    <div className="text-sm">
                      {lead.website_url ? (
                        <a href={lead.website_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                          {lead.website_url}
                        </a>
                      ) : "Not provided"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground mb-1">
                      LinkedIn
                    </div>
                    <div className="text-sm">
                      {lead.linkedin_url ? (
                        <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                          {lead.linkedin_url}
                        </a>
                      ) : "Not provided"}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ── Tab: Notes & Context ── */}
        {activeTab === "notes" && (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Card id="section-notes">
                <CardHeader>
                  <CardTitle className="text-base">Internal Notes</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Textarea
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="Add an internal note..."
                      className="min-h-[80px]"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleAddNote();
                      }}
                    />
                    <Button size="sm" onClick={handleAddNote} disabled={!noteText.trim()}>
                      Add Note
                    </Button>
                  </div>
                  {notes.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No notes yet.</p>
                  ) : (
                    <div className="space-y-3 border-t border-border pt-4">
                      {notes.map((note) => (
                        <div key={note.id} className="rounded-lg border border-border bg-background p-3 space-y-2">
                          {editingNoteId === note.id ? (
                            <div className="space-y-2">
                              <Textarea
                                value={editNoteText}
                                onChange={(e) => setEditNoteText(e.target.value)}
                                className="min-h-[80px]"
                                autoFocus
                              />
                              <div className="flex gap-2">
                                <Button size="sm" onClick={() => handleSaveNote(note.id)} disabled={!editNoteText.trim()}>
                                  Save
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => { setEditingNoteId(null); setEditNoteText(""); }}>
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <p className="text-sm whitespace-pre-wrap text-foreground">{note.body}</p>
                              <div className="flex items-center justify-between">
                                <span className="text-xs text-muted-foreground">
                                  {note.occurred_at
                                    ? formatDistanceToNow(new Date(note.occurred_at), { addSuffix: true })
                                    : ""}
                                </span>
                                <div className="flex gap-1">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 px-2 text-xs"
                                    onClick={() => { setEditingNoteId(note.id); setEditNoteText(note.body || ""); }}
                                  >
                                    Edit
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                                    onClick={() => handleDeleteNote(note.id)}
                                  >
                                    Delete
                                  </Button>
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Context Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {detailRow("Personalization Note", lead.personalization_note)}
                  {detailRow("Outreach Angle", lead.outreach_angle)}
                  {detailRow("Outcome Note", lead.outcome_note)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Recent Activity</CardTitle>
                </CardHeader>
                <CardContent>
                  {activities.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No activity yet.</p>
                  ) : (
                    <ol className="relative border-l border-border ml-2 space-y-3">
                      {activities.slice(0, 5).map((a) => (
                        <li key={a.id} className="ml-4">
                          <span className="absolute -left-1.5 mt-1.5 h-2.5 w-2.5 rounded-full border border-background bg-border" />
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-xs font-medium text-foreground">
                              {ACTIVITY_LABELS[a.activity_type] ?? a.activity_type}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {a.occurred_at
                                ? formatDistanceToNow(new Date(a.occurred_at), { addSuffix: true })
                                : ""}
                            </span>
                          </div>
                          {a.body && (
                            <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-2">{a.body}</p>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}
                  {activities.length > 5 && (
                    <button
                      type="button"
                      className="mt-3 text-xs text-primary hover:underline"
                      onClick={() => setActiveTab("history")}
                    >
                      View all activity →
                    </button>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ── Tab: Email ── */}
        {activeTab === "email" && (
          <Card id="section-email">
            <CardHeader>
              <CardTitle className="text-base">Send Email</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {lead.do_not_contact && (
                <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm font-medium text-destructive">
                  ⛔ Do Not Contact — outbound email is blocked for this lead. Remove the DNC flag in Edit to re-enable.
                </div>
              )}
              {emailSuccess && (
                <div className={`rounded-md p-3 text-sm ${emailSuccess.includes("test mode") ? "bg-amber-500/10 text-amber-700 dark:text-amber-400" : "bg-green-500/10 text-green-600"}`}>
                  {emailSuccess}
                </div>
              )}
              {emailError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {emailError}
                </div>
              )}
              {templates.length > 0 && (
                <div className="space-y-2">
                  <Label>Use a template</Label>
                  <Select
                    value=""
                    onValueChange={(tid) => {
                      const tpl = templates.find((t) => t.id === tid);
                      if (tpl) {
                        setEmailSubject(tpl.subject);
                        setEmailBody(tpl.body);
                        setEmailSuccess(null);
                      }
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select a template..." />
                    </SelectTrigger>
                    <SelectContent>
                      {templates.map((t) => (
                        <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-2">
                <Label htmlFor="email-subject">Subject</Label>
                <Input
                  id="email-subject"
                  value={emailSubject}
                  onChange={(e) => { setEmailSubject(e.target.value); setEmailSuccess(null); }}
                  placeholder="Email subject..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email-body">Body</Label>
                <Textarea
                  id="email-body"
                  value={emailBody}
                  onChange={(e) => { setEmailBody(e.target.value); setEmailSuccess(null); }}
                  placeholder="Write your email..."
                  className="min-h-[120px]"
                />
              </div>
              <Button
                size="sm"
                onClick={handleSendEmail}
                disabled={emailSending || !emailSubject.trim() || !emailBody.trim() || lead.do_not_contact}
              >
                {emailSending ? "Sending..." : "Send Email"}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* ── Tab: Activity History ── */}
        {activeTab === "history" && (
          <Card id="section-history">
            <CardHeader>
              <CardTitle className="text-base">Activity History</CardTitle>
            </CardHeader>
            <CardContent>
              {activities.length === 0 ? (
                <p className="text-sm text-muted-foreground">No activity yet.</p>
              ) : (
                <ol className="relative border-l border-border ml-2 space-y-4">
                  {activities.map((a) => (
                    <li key={a.id} className="ml-4">
                      <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-background bg-border" />
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-medium text-foreground">
                          {ACTIVITY_LABELS[a.activity_type] ?? a.activity_type}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {a.occurred_at
                            ? formatDistanceToNow(new Date(a.occurred_at), { addSuffix: true })
                            : ""}
                        </span>
                      </div>
                      {a.body && (
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap line-clamp-3">{a.body}</p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <CardTitle>Edit Lead</CardTitle>
          <Button type="button" variant="outline" onClick={handleCancelEdit}>
            Cancel
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">First Name</Label>
                <Input
                  id="first_name"
                  value={form.first_name}
                  onChange={(e) => set("first_name", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Last Name</Label>
                <Input
                  id="last_name"
                  value={form.last_name}
                  onChange={(e) => set("last_name", e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="business_name">Business Name</Label>
              <Input
                id="business_name"
                value={form.business_name}
                onChange={(e) => set("business_name", e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  placeholder="+1 (555) 000-0000"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="segment">Segment</Label>
              <Select value={form.segment_id} onValueChange={(v) => set("segment_id", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent>
                  {segments.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="niche">Niche</Label>
              <Input
                id="niche"
                value={form.niche}
                onChange={(e) => set("niche", e.target.value)}
              />
            </div>

            <button
              type="button"
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
              Advanced fields
            </button>

            {showAdvanced && (
              <div className="space-y-4 border-t border-border pt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="website_url">Website</Label>
                    <Input
                      id="website_url"
                      value={form.website_url}
                      onChange={(e) => set("website_url", e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="linkedin_url">LinkedIn</Label>
                    <Input
                      id="linkedin_url"
                      value={form.linkedin_url}
                      onChange={(e) => set("linkedin_url", e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="contact_path">Contact Path</Label>
                    <Select value={form.contact_path} onValueChange={(v) => set("contact_path", v)}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select..." />
                      </SelectTrigger>
                      <SelectContent>
                        {CONTACT_PATHS.map((c) => (
                          <SelectItem key={c} value={c}>
                            {c}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="team_size_estimate">Team Size</Label>
                    <Input
                      id="team_size_estimate"
                      type="number"
                      value={form.team_size_estimate}
                      onChange={(e) => set("team_size_estimate", e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="location_text">Location</Label>
                  <Input
                    id="location_text"
                    value={form.location_text}
                    onChange={(e) => set("location_text", e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="source_url">Source URL</Label>
                  <Input
                    id="source_url"
                    value={form.source_url}
                    onChange={(e) => set("source_url", e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="personalization_note">Personalization Note</Label>
                  <Textarea
                    id="personalization_note"
                    value={form.personalization_note}
                    onChange={(e) => set("personalization_note", e.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="outreach_angle">Outreach Angle</Label>
                  <Textarea
                    id="outreach_angle"
                    value={form.outreach_angle}
                    onChange={(e) => set("outreach_angle", e.target.value)}
                  />
                </div>

                <div className="flex items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-3">
                  <input
                    type="checkbox"
                    id="do_not_contact"
                    checked={form.do_not_contact}
                    onChange={(e) => setForm((prev) => ({ ...prev, do_not_contact: e.target.checked }))}
                    className="h-4 w-4 accent-destructive"
                  />
                  <Label htmlFor="do_not_contact" className="cursor-pointer text-sm font-medium text-destructive">
                    Do Not Contact — block all outbound email to this lead
                  </Label>
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={saving}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
              <Button type="button" variant="outline" onClick={handleCancelEdit}>
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
