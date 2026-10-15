import { useState, useRef } from "react";
import * as api from "../api";
import type { ImportPreview, ImportCommitResult, ImportAction, ImportResult } from "../types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Upload, FileText, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [actions, setActions] = useState<Record<string, ImportAction>>({});
  const [result, setResult] = useState<ImportCommitResult | ImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setPreview(null);
    setActions({});
    setResult(null);
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError("");
    reset();
    try {
      const res = await api.importPreview(file);
      if (res.duplicate_count === 0 && res.errors.length === 0) {
        // No duplicates to review — commit immediately
        const committed = await api.importCommit(res.batch, {});
        setResult(committed);
      } else {
        setPreview(res);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const handleCommit = async () => {
    if (!preview) return;
    setImporting(true);
    setError("");
    try {
      const committed = await api.importCommit(preview.batch, actions);
      setResult(committed);
      setPreview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import commit failed");
    } finally {
      setImporting(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && f.name.endsWith(".csv")) {
      setFile(f);
      reset();
    }
  };

  const setAction = (row: number, action: ImportAction) => {
    setActions((prev) => ({ ...prev, [String(row)]: action }));
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Import Leads</CardTitle>
          <CardDescription>Upload a CSV file with your leads data</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
          >
            <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              {file ? file.name : "Drop a CSV file here or click to browse"}
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                reset();
              }}
            />
          </div>

          <div className="text-xs text-muted-foreground space-y-1">
            <p><strong>Supported columns:</strong> first_name, last_name, full_name, business_name (or company), email, phone, segment, niche, website_url (or website), linkedin_url (or linkedin), contact_path, location_text (or location), team_size_estimate (or team_size), source_url, personalization_note, outreach_angle, tags (comma-separated)</p>
            <p><strong>Duplicates:</strong> rows matching an existing lead by email (or phone) are flagged for review — you choose to update, merge, or skip each one. Rows without email and phone are never flagged.</p>
            <p><strong>Segments:</strong> the segment column matches your custom segments by name — &quot;Home Services&quot;, &quot;home_services&quot;, or &quot;home-services&quot; all resolve to the Home Services segment. Unrecognized values fall back to the built-in Coach / Consultant / Solopreneur / Other categories.</p>
          </div>

          {file && (
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
            </div>
          )}

          <Button onClick={handleImport} disabled={!file || importing}>
            {importing ? "Importing..." : "Import CSV"}
          </Button>

          {error && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>
          )}

          {result && (
            <div className="border border-border rounded-lg p-4 space-y-3">
              <h3 className="font-medium text-foreground">Import Results</h3>
              <div className="flex flex-wrap gap-4">
                {"inserted" in result && (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span className="text-sm">{result.inserted} inserted</span>
                  </div>
                )}
                {"accepted" in result && (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span className="text-sm">{result.accepted} accepted</span>
                  </div>
                )}
                {"updated" in result && result.updated > 0 && (
                  <span className="text-sm">{result.updated} updated</span>
                )}
                {"merged" in result && result.merged > 0 && (
                  <span className="text-sm">{result.merged} merged</span>
                )}
                {"skipped" in result && result.skipped > 0 && (
                  <span className="text-sm">{result.skipped} skipped</span>
                )}
                {"duplicates_skipped" in result && (result as ImportResult).duplicates_skipped ? (
                  <span className="text-sm">{(result as ImportResult).duplicates_skipped} duplicates skipped</span>
                ) : null}
                {"rejected" in result && (
                  <div className="flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-red-500" />
                    <span className="text-sm">{result.rejected} rejected</span>
                  </div>
                )}
              </div>
              {"errors" in result && result.errors.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Errors:</p>
                  {result.errors.map((e, i) => (
                    <p key={i} className="text-xs text-destructive">Row {e.row}: {e.error}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Review Duplicates
            </CardTitle>
            <CardDescription>
              {preview.new_count} new lead{preview.new_count === 1 ? "" : "s"} will be added.
              {" "}
              {preview.duplicate_count} possible duplicate{preview.duplicate_count === 1 ? "" : "s"} found —
              choose an action for each.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {preview.duplicates.map((d) => {
              const existingLabel =
                "lead_id" in d.existing
                  ? d.existing.full_name || d.existing.email || d.existing.lead_id
                  : `row ${d.existing.first_row} of this file`;
              const current = actions[String(d.row_number)] || "skip";
              return (
                <div key={d.row_number} className="rounded-lg border p-4 space-y-3">
                  <div className="text-sm font-medium">Row {d.row_number}</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="space-y-0.5">
                      <p className="font-medium text-muted-foreground uppercase tracking-wide">Incoming</p>
                      <p>{d.incoming.full_name || "—"}{d.incoming.business_name ? ` — ${d.incoming.business_name}` : ""}</p>
                      <p className="text-muted-foreground">{d.incoming.email || "no email"}{d.incoming.phone ? ` · ${d.incoming.phone}` : ""}</p>
                      {d.incoming_tags.length > 0 && <p className="text-muted-foreground">Tags: {d.incoming_tags.join(", ")}</p>}
                    </div>
                    <div className="space-y-0.5">
                      <p className="font-medium text-muted-foreground uppercase tracking-wide">Matches existing</p>
                      <p>{existingLabel}</p>
                      {"email" in d.existing && (
                        <p className="text-muted-foreground">{d.existing.email || "no email"}{"phone" in d.existing && d.existing.phone ? ` · ${d.existing.phone}` : ""}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(["skip", "update", "merge"] as ImportAction[]).map((a) => (
                      <Button
                        key={a}
                        size="sm"
                        variant={current === a ? "default" : "outline"}
                        onClick={() => setAction(d.row_number, a)}
                      >
                        {a === "skip" ? "Skip" : a === "update" ? "Update (fill blanks)" : "Merge (+ tags)"}
                      </Button>
                    ))}
                  </div>
                </div>
              );
            })}

            {preview.errors.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Unparseable rows (will be skipped):</p>
                {preview.errors.map((e, i) => (
                  <p key={i} className="text-xs text-destructive">Row {e.row}: {e.error}</p>
                ))}
              </div>
            )}

            <Button onClick={handleCommit} disabled={importing}>
              {importing ? "Applying..." : "Complete Import"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
