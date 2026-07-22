// ─── Enums ────────────────────────────────────────────────────────────────

export type SegmentValue = string;
export type ContactPath = "EMAIL" | "FORM" | "DM" | "OTHER";
export type PriorityTier = "A" | "B" | "C";
export type LeadStatus =
  | "NEW"
  | "SCORED"
  | "READY_TO_CONTACT"
  | "CONTACTED"
  | "FOLLOW_UP_1"
  | "FOLLOW_UP_2"
  | "REPLIED"
  | "CALL_BOOKED"
  | "WON"
  | "CLIENT"
  | "LOST"
  | "NURTURE";

export type ActivityType =
  | "NOTE"
  | "STATUS_CHANGE"
  | "OUTREACH_SENT"
  | "FOLLOW_UP_SENT"
  | "REPLY_RECEIVED"
  | "CALL_BOOKED"
  | "OTHER";

// ─── Models ───────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
}

export interface Lead {
  id: string;
  owner_user_id: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  business_name: string | null;
  segment: SegmentValue | null;
  segment_id?: string | null;
  segment_label?: string | null;
  niche: string | null;
  website_url: string | null;
  email: string | null;
  contact_path: ContactPath | null;
  linkedin_url: string | null;
  location_text: string | null;
  team_size_estimate: number | null;
  source_url: string | null;
  personalization_note: string | null;
  outreach_angle: string | null;
  offer_clarity_score: number;
  bottleneck_evidence_score: number;
  buying_signal_score: number;
  decision_maker_access_score: number;
  contactability_score: number;
  strategic_fit_score: number;
  total_score: number;
  priority_tier: PriorityTier;
  status: LeadStatus;
  last_contacted_at: string | null;
  follow_up_count: number;
  next_follow_up_at: string | null;
  outcome_note: string | null;
  created_at: string | null;
  updated_at: string | null;
}
export interface Activity {
  id: string;
  lead_id: string;
  user_id: string;
  activity_type: ActivityType;
  body: string | null;
  occurred_at: string | null;
  created_at: string | null;
}

export interface SegmentOption {
  id: string;
  owner_user_id: string;
  key: string;
  label: string;
  sort_order: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

// ─── API Responses ────────────────────────────────────────────────────────

export interface AuthResponse {
  token: string;
  user: User;
}

export interface LeadsResponse {
  total: number;
  page: number;
  page_size: number;
  items: Lead[];
}

export interface DashboardData {
  leads_contacted_week: number;
  replies_week: number;
  calls_booked_week: number;
  wins_month: number;
  follow_ups_due_today: Lead[];
  overdue_follow_ups: Lead[];
}

export interface ImportResult {
  accepted: number;
  rejected: number;
  errors: { row: number; error: string }[];
}

export type PipelineData = Record<LeadStatus, Lead[]>;

// ─── Constants ────────────────────────────────────────────────────────────

export const STATUSES: LeadStatus[] = [
  "NEW", "SCORED", "READY_TO_CONTACT", "CONTACTED",
  "FOLLOW_UP_1", "FOLLOW_UP_2", "REPLIED", "CALL_BOOKED",
  "WON", "CLIENT", "LOST", "NURTURE",
];

export const CONTACT_PATHS: ContactPath[] = ["EMAIL", "FORM", "DM", "OTHER"];
export const PRIORITY_TIERS: PriorityTier[] = ["A", "B", "C"];

export const STATUS_LABELS: Record<LeadStatus, string> = {
  NEW: "New",
  SCORED: "Scored",
  READY_TO_CONTACT: "Ready to Contact",
  CONTACTED: "Contacted",
  FOLLOW_UP_1: "Follow-up 1",
  FOLLOW_UP_2: "Follow-up 2",
  REPLIED: "Replied",
  CALL_BOOKED: "Call Booked",
  WON: "Won",
  CLIENT: "Client",
  LOST: "Lost",
  NURTURE: "Nurture",
};
