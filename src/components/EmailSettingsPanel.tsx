/**
 * EmailSettingsPanel — Settings scaffold for future email provider configuration.
 *
 * STUB: fields are display-only; no save endpoint exists yet.
 *
 * To complete later:
 * 1. Build POST/PUT /api/settings/email backend route that persists config.
 * 2. Replace the placeholder notice with a real form wired to that endpoint.
 * 3. Add provider-specific fields (SMTP host/port, API key, from address, etc.)
 *    based on the chosen provider.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function EmailSettingsPanel() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Email Configuration</CardTitle>
        <CardDescription>
          Configure the outbound email provider used to send messages to leads.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-dashed border-border bg-muted/40 px-4 py-6 text-center text-sm text-muted-foreground space-y-1">
          <p className="font-medium">Email sending is not yet configured.</p>
          <p>
            To enable outbound email, add provider credentials here and wire them
            to <code className="text-xs bg-muted px-1 py-0.5 rounded">email_service.py</code>.
          </p>
          <p className="text-xs mt-2 opacity-70">
            Supported providers: SMTP, SendGrid, Resend, Postmark (see email_service.py).
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
