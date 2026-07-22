/**
 * EmailSettingsPanel — Email template management + provider config placeholder.
 */
import { useEffect, useState } from "react";
import * as api from "../api";
import type { EmailTemplate } from "../types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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

  // Create form
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editSaving, setEditSaving] = useState(false);

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

  useEffect(() => { load(); }, []);

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
      {/* Provider config placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Email Provider</CardTitle>
          <CardDescription>
            Configure the outbound email provider for sending messages to leads.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-dashed border-border bg-muted/40 px-4 py-5 text-center text-sm text-muted-foreground space-y-1">
            <p className="font-medium">No provider configured.</p>
            <p>
              Add credentials in{" "}
              <code className="text-xs bg-muted px-1 py-0.5 rounded">email_service.py</code>{" "}
              to enable live sending.
            </p>
          </div>
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
