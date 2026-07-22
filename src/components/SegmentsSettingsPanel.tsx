import { useEffect, useState } from "react";
import { listSegments, createSegment } from "../api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

type SegmentOption = {
  id: string;
  key: string;
  label: string;
  sort_order?: number;
  is_active?: boolean;
};

export default function SegmentsSettingsPanel() {
  const [segments, setSegments] = useState<SegmentOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [label, setLabel] = useState("");
  const [keyValue, setKeyValue] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function loadSegments() {
    try {
      setLoading(true);
      setError(null);
      const data = await listSegments();
      setSegments(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load segments");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSegments();
  }, []);

  async function handleCreateSegment(e: React.FormEvent) {
    e.preventDefault();

    try {
      setCreating(true);
      setCreateError(null);

      await createSegment({
        label,
        key: keyValue,
      });

      setLabel("");
      setKeyValue("");
      await loadSegments();
    } catch (err: any) {
      setCreateError(err?.message || "Failed to create segment");
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading segments...</div>;
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Segments</CardTitle>
          <CardDescription>
            Create and manage custom lead segments for your CRM.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <form onSubmit={handleCreateSegment} className="space-y-4">
            {createError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {createError}
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="segment-label">Label</Label>
                <Input
                  id="segment-label"
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="Medspa"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="segment-key">Key</Label>
                <Input
                  id="segment-key"
                  type="text"
                  value={keyValue}
                  onChange={(e) => setKeyValue(e.target.value)}
                  placeholder="medspa"
                />
              </div>
            </div>

            <div className="flex justify-start">
              <Button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create segment"}
              </Button>
            </div>
          </form>

          <div className="border-t border-border pt-4">
            {segments.length === 0 ? (
              <p className="text-sm text-muted-foreground">No segments yet.</p>
            ) : (
              <ul className="space-y-2">
                {segments.map((segment) => (
                  <li
                    key={segment.id}
                    className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="font-medium">{segment.label}</div>
                      <div className="text-sm text-muted-foreground">
                        {segment.key}
                      </div>
                    </div>

                    <div className="text-xs text-muted-foreground">
                      {segment.is_active ? "Active" : "Inactive"}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}