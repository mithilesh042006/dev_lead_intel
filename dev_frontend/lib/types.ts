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
