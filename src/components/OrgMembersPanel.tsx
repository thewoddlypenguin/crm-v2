import { useState, useEffect } from "react";
import type { OrgMember } from "../types";
import * as api from "../api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { UserPlus, Trash2, ShieldCheck, User } from "lucide-react";

export default function OrgMembersPanel() {
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add member form
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("member");
  const [adding, setAdding] = useState(false);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);

  const load = async () => {
    try {
      setMembers(await api.listOrgMembers());
    } catch {
      setError("Failed to load members");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setAdding(true);
    setAddError(null);
    setTempPassword(null);
    try {
      const result = await api.addOrgMember({ email: email.trim(), full_name: fullName.trim() || undefined, role });
      if (result.temp_password) setTempPassword(result.temp_password);
      setEmail("");
      setFullName("");
      setRole("member");
      await load();
    } catch (err: unknown) {
      const msg = (err as { detail?: string })?.detail ?? "Failed to add member";
      setAddError(msg);
    } finally {
      setAdding(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api.updateOrgMemberRole(userId, newRole);
      await load();
    } catch (err: unknown) {
      alert((err as { detail?: string })?.detail ?? "Failed to update role");
    }
  };

  const handleRemove = async (member: OrgMember) => {
    if (!confirm(`Remove ${member.email} from the organization?`)) return;
    try {
      await api.removeOrgMember(member.user_id);
      await load();
    } catch (err: unknown) {
      alert((err as { detail?: string })?.detail ?? "Failed to remove member");
    }
  };

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (error) return <p className="text-sm text-destructive">{error}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Organization Members</h2>
        <p className="text-sm text-muted-foreground">
          Manage who has access to your CRM. Owners can add and remove members.
        </p>
      </div>

      {/* Member list */}
      <div className="border border-border rounded-lg divide-y divide-border">
        {members.map((m) => (
          <div key={m.user_id} className="flex items-center justify-between px-4 py-3 gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center shrink-0">
                {m.role === "owner"
                  ? <ShieldCheck className="h-4 w-4 text-primary" />
                  : <User className="h-4 w-4 text-muted-foreground" />
                }
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">
                  {m.full_name || m.email}
                  {m.is_self && <span className="ml-2 text-xs text-muted-foreground">(you)</span>}
                </p>
                {m.full_name && (
                  <p className="text-xs text-muted-foreground truncate">{m.email}</p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {m.is_self ? (
                <Badge variant="outline" className="capitalize">{m.role}</Badge>
              ) : (
                <Select value={m.role} onValueChange={(v) => handleRoleChange(m.user_id, v)}>
                  <SelectTrigger className="w-[110px] h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="owner">Owner</SelectItem>
                    <SelectItem value="member">Member</SelectItem>
                  </SelectContent>
                </Select>
              )}
              {!m.is_self && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => handleRemove(m)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Add member form */}
      <div className="border border-border rounded-lg p-4 space-y-4">
        <h3 className="text-sm font-semibold">Add Member</h3>
        <form onSubmit={handleAdd} className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              placeholder="Full name (optional)"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-3">
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="member">Member</SelectItem>
                <SelectItem value="owner">Owner</SelectItem>
              </SelectContent>
            </Select>
            <Button type="submit" disabled={adding} className="gap-2">
              <UserPlus className="h-4 w-4" />
              {adding ? "Adding…" : "Add Member"}
            </Button>
          </div>
          {addError && <p className="text-sm text-destructive">{addError}</p>}
        </form>
      </div>

      {/* Temp password callout */}
      {tempPassword && (
        <div className="border border-yellow-500/40 bg-yellow-500/10 rounded-lg p-4 space-y-1">
          <p className="text-sm font-semibold text-yellow-600 dark:text-yellow-400">
            Account created — share this temporary password
          </p>
          <p className="font-mono text-sm bg-muted rounded px-2 py-1 inline-block select-all">
            {tempPassword}
          </p>
          <p className="text-xs text-muted-foreground">
            This is shown once. The member should log in and change it.
          </p>
        </div>
      )}
    </div>
  );
}
