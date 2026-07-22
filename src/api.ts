import type {
  AuthResponse,
  DashboardData,
  EmailSendRequest,
  EmailSettings,
  EmailTemplate,
  ImportResult,
  Lead,
  LeadsResponse,
  LeadStatus,
  PipelineData,
  Activity,
  PriorityTier,
  SegmentValue,
  SegmentOption,
} from "./types";

const BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("crm_token");
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options.headers,
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("crm_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  return res.json();
}

// ─── Auth ────────────────────────────────────────────────────────────────

export async function register(email: string, password: string, full_name?: string): Promise<AuthResponse> {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name }),
  });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe(): Promise<{ id: string; email: string; full_name: string | null }> {
  return request("/auth/me");
}

// ─── Segments ────────────────────────────────────────────────────────────

export async function listSegments(include_inactive = false): Promise<SegmentOption[]> {
  const sp = new URLSearchParams();
  if (include_inactive) sp.set("include_inactive", "true");
  return request(`/segments?${sp.toString()}`);
}

export async function createSegment(data: {
  key: string;
  label: string;
  sort_order?: number;
  is_active?: boolean;
}): Promise<SegmentOption> {
  return request("/segments", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSegment(
  id: string,
  data: {
    key?: string;
    label?: string;
    sort_order?: number;
    is_active?: boolean;
  }
): Promise<SegmentOption> {
  return request(`/segments/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ─── Leads ───────────────────────────────────────────────────────────────

export async function listLeads(params?: {
  search?: string;
  status?: LeadStatus;
  priority?: PriorityTier;
  segment_id?: string;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}): Promise<LeadsResponse> {

  const sp = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") sp.set(k, String(v));
    });
  }
  return request(`/leads?${sp.toString()}`);
}

export async function createLead(data: Record<string, unknown>): Promise<Lead> {
  return request("/leads", { method: "POST", body: JSON.stringify(data) });
}

export async function getLead(id: string): Promise<Lead> {
  return request(`/leads/${id}`);
}

export async function updateLead(id: string, data: Record<string, unknown>): Promise<Lead> {
  return request(`/leads/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteLead(id: string): Promise<void> {
  await request(`/leads/${id}`, { method: "DELETE" });
}

export async function changeStatus(id: string, status: LeadStatus): Promise<Lead> {
  return request(`/leads/${id}/status`, { method: "POST", body: JSON.stringify({ status }) });
}

export async function bulkStatusChange(ids: string[], status: LeadStatus): Promise<{ updated: number }> {
  return request("/leads/bulk-status", { method: "POST", body: JSON.stringify({ lead_ids: ids, status }) });
}

export async function bulkSegmentChange(
  ids: string[],
  segment_id: string
): Promise<{ updated: number }> {
  return request("/leads/bulk-segment", {
    method: "POST",
    body: JSON.stringify({ lead_ids: ids, segment_id }),
  });
}


// ─── Activities ──────────────────────────────────────────────────────────

export async function listActivities(leadId: string): Promise<Activity[]> {
  return request(`/leads/${leadId}/activities`);
}

export async function createActivity(leadId: string, data: { activity_type: string; body?: string; occurred_at?: string }): Promise<Activity> {
  return request(`/leads/${leadId}/activities`, { method: "POST", body: JSON.stringify(data) });
}

export async function updateActivity(leadId: string, activityId: string, body: string): Promise<Activity> {
  return request(`/leads/${leadId}/activities/${activityId}`, {
    method: "PUT",
    body: JSON.stringify({ body }),
  });
}

export async function deleteActivity(leadId: string, activityId: string): Promise<void> {
  await request(`/leads/${leadId}/activities/${activityId}`, { method: "DELETE" });
}

// ─── Email ────────────────────────────────────────────────────────────────

/** Send an email to a lead. Returns the logged OUTREACH_SENT activity (+ simulated flag) on success. */
export async function sendLeadEmail(leadId: string, data: EmailSendRequest): Promise<Activity & { simulated?: boolean }> {
  return request(`/leads/${leadId}/email`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ─── Email Settings ───────────────────────────────────────────────────────

export async function getEmailSettings(): Promise<EmailSettings> {
  return request("/email-settings");
}

export async function saveEmailSettings(data: Partial<Omit<EmailSettings, "id" | "updated_at">>): Promise<EmailSettings> {
  return request("/email-settings", { method: "PUT", body: JSON.stringify(data) });
}

// ─── Email Templates ──────────────────────────────────────────────────────

export async function listEmailTemplates(): Promise<EmailTemplate[]> {
  return request("/email-templates");
}

export async function createEmailTemplate(data: { name: string; subject: string; body: string }): Promise<EmailTemplate> {
  return request("/email-templates", { method: "POST", body: JSON.stringify(data) });
}

export async function updateEmailTemplate(id: string, data: { name?: string; subject?: string; body?: string }): Promise<EmailTemplate> {
  return request(`/email-templates/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deleteEmailTemplate(id: string): Promise<void> {
  await request(`/email-templates/${id}`, { method: "DELETE" });
}

// ─── Dashboard ───────────────────────────────────────────────────────────

export async function getDashboard(): Promise<DashboardData> {
  return request("/dashboard");
}

// ─── Pipeline ────────────────────────────────────────────────────────────

export async function getPipeline(): Promise<PipelineData> {
  return request("/pipeline");
}

// ─── CSV Import/Export ───────────────────────────────────────────────────

export async function importCSV(file: File): Promise<ImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE}/import/csv`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Import failed");
  }
  return res.json();
}

export function exportCSVUrl(params?: {
  search?: string;
  status?: LeadStatus;
  priority?: PriorityTier;
  segment?: SegmentValue;
}): string {
  const sp = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") sp.set(k, String(v));
    });
  }
// Return direct URL for download - auth-sensitive downloads should use fetch/downloadCSV
return `${BASE}/export/csv?${sp.toString()}`;
}

export async function downloadCSV(params?: {
  search?: string;
  status?: LeadStatus;
  priority?: PriorityTier;
  segment?: SegmentValue;
}): Promise<Blob> {
  const sp = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") sp.set(k, String(v));
    });
  }
  const res = await fetch(`${BASE}/export/csv?${sp.toString()}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Export failed");
  return res.blob();
}
