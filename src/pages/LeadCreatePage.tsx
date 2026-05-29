import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { SEGMENTS, CONTACT_PATHS, SEGMENT_LABELS } from "../types";
import type { Segment, ContactPath } from "../types";
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

export default function LeadCreatePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    business_name: "",
    segment: "" as string,
    niche: "",
    email: "",
    website_url: "",
    contact_path: "" as string,
    linkedin_url: "",
    location_text: "",
    team_size_estimate: "",
    source_url: "",
    personalization_note: "",
    outreach_angle: "",
  });

  const set = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data: Record<string, unknown> = {
        first_name: form.first_name || null,
        last_name: form.last_name || null,
        business_name: form.business_name || null,
        segment: form.segment || null,
        niche: form.niche || null,
        email: form.email || null,
        website_url: form.website_url || null,
        contact_path: form.contact_path || null,
        linkedin_url: form.linkedin_url || null,
        location_text: form.location_text || null,
        team_size_estimate: form.team_size_estimate ? parseInt(form.team_size_estimate) : null,
        source_url: form.source_url || null,
        personalization_note: form.personalization_note || null,
        outreach_angle: form.outreach_angle || null,
      };
      const lead = await api.createLead(data);
      navigate(`/leads/${lead.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create lead");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>New Lead</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">First Name</Label>
                <Input id="first_name" value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Last Name</Label>
                <Input id="last_name" value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="business_name">Business Name</Label>
              <Input id="business_name" value={form.business_name} onChange={(e) => set("business_name", e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="segment">Segment</Label>
                <Select value={form.segment} onValueChange={(v) => set("segment", v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select..." />
                  </SelectTrigger>
                  <SelectContent>
                    {SEGMENTS.map((s) => (
                      <SelectItem key={s} value={s}>{SEGMENT_LABELS[s]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="niche">Niche</Label>
              <Input id="niche" value={form.niche} onChange={(e) => set("niche", e.target.value)} />
            </div>

            {/* Advanced fields */}
            <button
              type="button"
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              Advanced fields
            </button>

            {showAdvanced && (
              <div className="space-y-4 border-t border-border pt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="website_url">Website</Label>
                    <Input id="website_url" value={form.website_url} onChange={(e) => set("website_url", e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="linkedin_url">LinkedIn</Label>
                    <Input id="linkedin_url" value={form.linkedin_url} onChange={(e) => set("linkedin_url", e.target.value)} />
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
                          <SelectItem key={c} value={c}>{c}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="team_size_estimate">Team Size</Label>
                    <Input id="team_size_estimate" type="number" value={form.team_size_estimate} onChange={(e) => set("team_size_estimate", e.target.value)} />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="location_text">Location</Label>
                  <Input id="location_text" value={form.location_text} onChange={(e) => set("location_text", e.target.value)} />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="source_url">Source URL</Label>
                  <Input id="source_url" value={form.source_url} onChange={(e) => set("source_url", e.target.value)} />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="personalization_note">Personalization Note</Label>
                  <Textarea id="personalization_note" value={form.personalization_note} onChange={(e) => set("personalization_note", e.target.value)} />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="outreach_angle">Outreach Angle</Label>
                  <Textarea id="outreach_angle" value={form.outreach_angle} onChange={(e) => set("outreach_angle", e.target.value)} />
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={loading}>
                {loading ? "Creating..." : "Create Lead"}
              </Button>
              <Button type="button" variant="outline" onClick={() => navigate("/leads")}>
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
