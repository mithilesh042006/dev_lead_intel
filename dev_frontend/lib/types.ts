// Mirrors app/schemas/api.py on the backend. Keep in sync when that changes.

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "partial"
  | "failed"
  | "empty"
  | "cancelled";

export type Priority = "HOT" | "WARM" | "COLD" | "LOW";

export interface SearchBody {
  location: string;
  category: string;
  min_rating: number;
  max_rating: number;
  minimum_reviews: number;
  limit: number;
  max_places?: number | null;
  strict_filters?: boolean;
}

export interface Evidence {
  review_text: string;
  review_rating: number | null;
  review_date: string | null;
  review_url: string | null;
  pain_point: string;
  pain_category: string;
  severity: string;
  customer_impact: string;
  business_impact: string;
  recommended_solution: string;
  confidence: number;
}

export interface Scores {
  software_pain_score: number;
  business_potential_score: number;
  review_evidence_score: number;
  digital_presence_score: number;
  contactability_score: number;
  lead_score: number;
  priority: Priority;
  notes: string[];
}

export interface Lead {
  lead_id: string;
  company_name: string;
  category: string;
  rating: number | null;
  total_reviews: number;
  phone: string | null;
  email: string | null;
  website: string | null;
  address: string;
  city: string;
  google_maps_url: string | null;
  latitude: number | null;
  longitude: number | null;

  pain_point: string;
  pain_category: string;
  pain_severity: string;
  customer_impact: string;
  business_impact: string;
  confidence: number;

  primary_opportunity: string;
  secondary_opportunities: string[];

  technology_signals: string[];
  website_reachable: boolean;

  scores: Scores;
  sales_pitch: string;
  evidence: Evidence[];
}

export interface Job {
  job_id: string;
  status: JobStatus;
  stage: string;
  message: string;
  progress: number;
  location: string;
  category: string;
  min_rating: number;
  max_rating: number;
  minimum_reviews: number;
  requested_leads: number;
  created_at: string;
  completed_at: string | null;
  lead_count: number;
  warnings: string[];
  stats: Record<string, unknown>;
  has_csv: boolean;
}

export interface LeadsResponse {
  job_id: string;
  status: JobStatus;
  count: number;
  leads: Lead[];
}

export const TERMINAL_STATUSES: JobStatus[] = [
  "completed",
  "partial",
  "failed",
  "empty",
  "cancelled",
];

export function isTerminal(status: JobStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

// --- Saved leads (§28) -----------------------------------------------------

export interface SavedLead extends Lead {
  source_location: string;
  source_category: string;
  llm_model: string | null;
  is_manual: boolean;
  saved_at: string;
}

export interface SavedLeadsResponse {
  total: number;
  count: number;
  leads: SavedLead[];
}

export interface SaveLeadsResult {
  created: number;
  updated: number;
  lead_ids: string[];
}

// --- Follow-ups ------------------------------------------------------------

export interface FollowUp {
  id: number;
  happened_on: string;
  method: string;
  outcome: string;
  notes: string;
  next_followup_on: string | null;
  created_at: string;
}

export interface FollowUpBody {
  happened_on: string;
  method: string;
  outcome: string;
  notes: string;
  next_followup_on: string | null;
}

export interface FollowUpsResponse {
  lead_id: string;
  count: number;
  methods: string[];
  followups: FollowUp[];
}

// --- Dashboard -------------------------------------------------------------

export interface DashboardLeadRef {
  lead_id: string;
  company_name: string;
  lead_score: number;
  priority: Priority;
  city: string;
  pain_category: string;
  saved_at: string;
  last_followup_on: string | null;
  next_followup_on: string | null;
}

export interface Dashboard {
  total_leads: number;
  average_score: number;
  top_score: number;
  by_priority: { priority: Priority; count: number }[];
  by_pain_category: { category: string; count: number }[];
  total_followups: number;
  leads_contacted: number;
  leads_never_contacted: number;
  overdue: DashboardLeadRef[];
  due_soon: DashboardLeadRef[];
  needs_attention: DashboardLeadRef[];
  recent: DashboardLeadRef[];
}

// --- Manual lead entry -----------------------------------------------------

export interface ManualLeadBody {
  company_name: string;
  category: string;
  city: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  google_maps_url: string;
  rating: number | null;
  total_reviews: number;
  pain_point: string;
  pain_category: string;
  pain_severity: string;
  business_impact: string;
  primary_opportunity: string;
  technology_signals: string;
  sales_pitch: string;
  priority: Priority;
}

export interface ManualLeadOptions {
  pain_categories: string[];
  severities: string[];
  priorities: Priority[];
}
