import { useEffect, useState } from "react";
import * as api from "../api";
import type { GmailStatus } from "../types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function GmailSettingsPanel() {
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  async function load() {
    try {
      setLoading(true);
      const s = await api.getGmailStatus();
      setStatus(s);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load Gmail status");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleConnect() {
    try {
      const { auth_url } = await api.getGmailAuthUrl();
      // Redirect to Google OAuth
      window.location.href = auth_url;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start Gmail connection");
    }
  }

  async function handleDisconnect() {
    if (!confirm("Disconnect Gmail? This will remove sync and stop matching emails.")) return;
    try {
      await api.gmailDisconnect();
      setStatus(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to disconnect");
    }
  }

  async function handleToggleSync() {
    try {
      setToggling(true);
      const result = await api.gmailSyncToggle();
      setStatus((prev) => prev ? { ...prev, sync_enabled: result.sync_enabled } : null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to toggle sync");
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Gmail Sync</CardTitle>
          <CardDescription>
            Connect your Gmail account to automatically sync emails involving your leads. 
            Matched messages appear in the lead's activity feed.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive mb-4">
              {error}
            </div>
          )}
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : !status?.connected ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                No Gmail account connected. Connect to sync emails with your leads.
              </p>
              <Button onClick={handleConnect}>Connect Gmail</Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-border bg-background p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Connected account</span>
                  <span className="text-sm text-muted-foreground">{status.google_email}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Sync enabled</span>
                  <span className="text-sm">{status.sync_enabled ? "Yes" : "No"}</span>
                </div>
                {status.last_sync_at && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Last sync</span>
                    <span className="text-sm text-muted-foreground">
                      {new Date(status.last_sync_at).toLocaleString()}
                    </span>
                  </div>
                )}
                {status.last_error && (
                  <div className="rounded-md bg-destructive/10 p-2 text-xs text-destructive">
                    Last error: {status.last_error}
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleToggleSync} disabled={toggling}>
                  {toggling ? "Toggling..." : status.sync_enabled ? "Pause Sync" : "Resume Sync"}
                </Button>
                <Button variant="destructive" onClick={handleDisconnect}>
                  Disconnect
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}