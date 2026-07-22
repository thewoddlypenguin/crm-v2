/**
 * EmailSettingsPanel — Email provider config + template management.
 */
import { useEffect, useState } from "react";
import * as api from "../api";
import type { EmailSettings, EmailTemplate } from "../types";
import { EMAIL_PROVIDERS } from "../types";
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
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function EmailSettingsPanel() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Provider config state
  const [cfg, setCfg] = useState<EmailSettings | null>(null);
  const [cfgLoading, setCfgLoading] = useState(true);
  const [cfgSaving, setCfgSaving] = useState(false);
  const [cfgError, setCfgError] = useState<string | null>(null);
  const [cfgSuccess, setCfgSuccess] = useState(false);
  const [cfgForm, setCfgForm] = useState({
    provider: "none",
    from_email: "",
    from_name: "",
    reply_to_email: "",
    test_mode_enabled: true,
  });

  // Template create form
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Template edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  async function loadCfg() {
    try {
      setCfgLoading(true);
      const s = await api.getEmailSettings();
      setCfg(s);
      setCfgForm({
        provider: s.provider ?? "none",
        from_email: s.from_email ?? "",
        from_name: s.from_name ?? "",
        reply_to_email: s.reply_to_email ?? "",
        test_mode_enabled: s.test_mode_enabled,
      });
    } catch {
      // non-fatal — leave defaults
    } finally {
      setCfgLoading(false);
    }
  }

  async function load() {
    try {
      setLoading(true);
      setError(null);
      setTemplates(await api.listEmailTemplates());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadCfg(); load(); }, []);

  async function handleSaveCfg(e: React.FormEvent) {
    e.preventDefault();
    try {
      setCfgSaving(true);
      setCfgError(null);
      setCfgSuccess(false);
      const saved = await api.saveEmailSettings({
        provider: (cfgForm.provider && cfgForm.provider !== "none") ? cfgForm.provider : null,
        from_email: cfgForm.from_email || null,
        from_name: cfgForm.from_name || null,
        reply_to_email: cfgForm.reply_to_email || null,
        test_mode_enabled: cfgForm.test_mode_enabled,
      });
      setCfg(saved);
      setCfgSuccess(true);
    } catch (err: unknown) {
      setCfgError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setCfgSaving(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !subject.trim() || !body.trim()) return;
    try {
      setCreating(true);
      setCreateError(null);
      await api.createEmailTemplate({ name: name.trim(), subject: subject.trim(), body: body.trim() });
      setName(""); setSubject(""); setBody("");
      await load();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Failed to create template");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(t: EmailTemplate) {
    setEditingId(t.id);
    setEditName(t.name);
    setEditSubject(t.subject);
    setEditBody(t.body);
  }

  async function handleSaveEdit(id: string) {
    try {
      setEditSaving(true);
      await api.updateEmailTemplate(id, { name: editName.trim(), subject: editSubject.trim(), body: editBody.trim() });
      setEditingId(null);
      await load();
    } catch {
      // leave edit open on error
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this template?")) return;
    try {
      await api.deleteEmailTemplate(id);
      await load();
    } catch {
      // silent
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      {/* Provider config form */}
      <Card>
        <CardHeader>
          <CardTitle>Email Provider</CardTitle>
          <CardDescription>
            Configure the outbound email provider and sender identity. Credentials (API keys, passwords) are set as server environment variables — not stored here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {cfgLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : (
            <form onSubmit={handleSaveCfg} className="space-y-4">
              {cfgSuccess && (
                <div className="rounded-md bg-green-500/10 p-3 text-sm text-green-600">Settings saved.</div>
              )}
              {cfgError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{cfgError}</div>
              )}

              <div className="space-y-2">
                <Label>Provider</Label>
                <Select
                  value={cfgForm.provider}
                  onValueChange={(v) => setCfgForm((f) => ({ ...f, provider: v, }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a provider..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {EMAIL_PROVIDERS.map((p) => (
                      <SelectItem key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="cfg-from-email">From Email</Label>
                  <Input
                    id="cfg-from-email"
                    type="email"
                    value={cfgForm.from_email}
                    onChange={(e) => setCfgForm((f) => ({ ...f, from_email: e.target.value }))}
                    placeholder="you@yourdomain.com"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cfg-from-name">From Name</Label>
                  <Input
                    id="cfg-from-name"
                    value={cfgForm.from_name}
                    onChange={(e) => setCfgForm((f) => ({ ...f, from_name: e.target.value }))}
                    placeholder="Your Name"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="cfg-reply-to">Reply-To Email</Label>
                <Input
                  id="cfg-reply-to"
                  type="email"
                  value={cfgForm.reply_to_email}
                  onChange={(e) => setCfgForm((f) => ({ ...f, reply_to_email: e.target.value }))}
                  placeholder="replies@yourdomain.com (optional)"
                />
              </div>

              {/* Test mode toggle */}
              <div className="flex items-start gap-3 rounded-lg border border-border p-3 bg-muted/30">
                <input
                  type="checkbox"
                  id="cfg-test-mode"
                  checked={cfgForm.test_mode_enabled}
                  onChange={(e) => setCfgForm((f) => ({ ...f, test_mode_enabled: e.target.checked }))}
                  className="mt-0.5 h-4 w-4 rounded border-border"
                />
                <div>
                  <Label htmlFor="cfg-test-mode" className="cursor-pointer font-medium">Test mode enabled</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    When on, emails are simulated and never delivered. Disable only when your provider credentials are ready.
                  </p>
                </div>
              </div>

              <Button type="submit" disabled={cfgSaving}>
                {cfgSaving ? "Saving..." : "Save settings"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      {/* Template management */}
      <Card>
        <CardHeader>
          <CardTitle>Email Templates</CardTitle>
          <CardDescription>
            Create reusable templates to pre-fill the compose form on lead pages.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Create form */}
          <form onSubmit={handleCreate} className="space-y-3">
            {createError && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">{createError}</div>
            )}
            <div className="space-y-2">
              <Label htmlFor="tpl-name">Template name</Label>
              <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Initial outreach" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tpl-subject">Subject</Label>
              <Input id="tpl-subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Quick question about your business" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tpl-body">Body</Label>
              <Textarea id="tpl-body" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Hi {{name}},..." className="min-h-[100px]" />
            </div>
            <Button type="submit" disabled={creating || !name.trim() || !subject.trim() || !body.trim()}>
              {creating ? "Creating..." : "Create template"}
            </Button>
          </form>

          {/* Template list */}
          <div className="border-t border-border pt-4">
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : templates.length === 0 ? (
              <p className="text-sm text-muted-foreground">No templates yet.</p>
            ) : (
              <ul className="space-y-3">
                {templates.map((t) =>
                  editingId === t.id ? (
                    <li key={t.id} className="rounded-lg border border-border bg-background p-3 space-y-3">
                      <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Name" />
                      <Input value={editSubject} onChange={(e) => setEditSubject(e.target.value)} placeholder="Subject" />
                      <Textarea value={editBody} onChange={(e) => setEditBody(e.target.value)} className="min-h-[80px]" />
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleSaveEdit(t.id)} disabled={editSaving}>
                          {editSaving ? "Saving..." : "Save"}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>
                          Cancel
                        </Button>
                      </div>
                    </li>
                  ) : (
                    <li key={t.id} className="rounded-lg border border-border bg-background p-3 space-y-1">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="font-medium text-sm">{t.name}</p>
                          <p className="text-xs text-muted-foreground truncate">{t.subject}</p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => startEdit(t)}>
                            Edit
                          </Button>
                          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-destructive hover:text-destructive" onClick={() => handleDelete(t.id)}>
                            Delete
                          </Button>
                        </div>
                      </div>
                    </li>
                  )
                )}
              </ul>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
