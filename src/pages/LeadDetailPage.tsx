import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CONTACT_PATHS, STATUS_LABELS } from "../types";
import type { ContactPath, Lead, SegmentOption } from "../types";
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

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    business_name: "",
    segment_id: "",
    niche: "",
    email: "",
    website_url: "",
    contact_path: "" as ContactPath | "",
    linkedin_url: "",
    location_text: "",
    team_size_estimate: "",
    source_url: "",
    personalization_note: "",
    outreach_angle: "",
  });

  const fillForm = (data: Lead) => {
    setForm({
      first_name: data.first_name || "",
      last_name: data.last_name || "",
      business_name: data.business_name || "",
      segment_id: data.segment_id || "",
      niche: data.niche || "",
      email: data.email || "",
      website_url: data.website_url || "",
      contact_path: (data.contact_path || "") as ContactPath | "",
      linkedin_url: data.linkedin_url || "",
      location_text: data.location_text || "",
      team_size_estimate:
        data.team_size_estimate != null ? String(data.team_size_estimate) : "",
      source_url: data.source_url || "",
      personalization_note: data.personalization_note || "",
      outreach_angle: data.outreach_angle || "",
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
        const [leadData, segmentOptions] = await Promise.all([
          api.getLead(id),
          api.listSegments(),
        ]);

        if (cancelled) return;

        setLead(leadData);
        setSegments(segmentOptions);
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

  if (!editing) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <Card className="overflow-hidden border-border/70">
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

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Contact details</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {detailRow("First Name", lead.first_name)}
                {detailRow("Last Name", lead.last_name)}
                {detailRow("Email", lead.email)}
                {detailRow("Contact Path", lead.contact_path)}
                {detailRow("Website", lead.website_url)}
                {detailRow("LinkedIn", lead.linkedin_url)}
                {detailRow("Location", lead.location_text)}
                {detailRow("Follow Up Count", lead.follow_up_count)}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Business profile</CardTitle>
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
                <CardTitle className="text-base">Notes and context</CardTitle>
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
                <CardTitle className="text-base">Lead scores</CardTitle>
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
                <CardTitle className="text-base">Total score</CardTitle>
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
          </div>
        </div>
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