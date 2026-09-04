// Client for the FastAPI backend (spec §26).
//
// No API keys live here. The browser only ever talks to our own backend, which
// holds the Apify and Gemini credentials server-side (§37).

import type {
  Dashboard,
  FollowUp,
  FollowUpBody,
  FollowUpsResponse,
  Job,
  ManualLeadBody,
  ManualLeadOptions,
  LeadsResponse,
  SaveLeadsResult,
  SavedLead,
  SavedLeadsResponse,
  SearchBody,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    // A rejected fetch() is indistinguishable from a CORS block: browsers hide
    // the reason from JavaScript on purpose. Naming both causes, because a
    // healthy backend that has not allowed this origin looks exactly like one
    // that is down — and the fix is completely different.
    throw new ApiError(
      `Could not reach the API at ${API_BASE}. Either it is not running, or ` +
        `it is running but has not allowed this site's origin — check ` +
        `CORS_ORIGINS on the backend includes ${
          typeof window === "undefined" ? "this site" : window.location.origin
        }.`,
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await describeError(response), response.status);
  }
  return (await response.json()) as T;
}

async function describeError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // FastAPI validation errors arrive as a list of {loc, msg}.
      return detail
        .map((d) => {
          const field = Array.isArray(d.loc) ? d.loc.at(-1) : undefined;
          return field ? `${field}: ${d.msg}` : d.msg;
        })
        .join("; ");
    }
  } catch {
    // fall through to the generic message
  }
  return `Request failed (${response.status})`;
}

export function startSearch(body: SearchBody): Promise<{ job_id: string }> {
  return request<{ job_id: string }>("/api/search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/jobs/${jobId}`);
}

export function getLeads(jobId: string): Promise<LeadsResponse> {
  return request<LeadsResponse>(`/api/leads?job_id=${encodeURIComponent(jobId)}`);
}

export function cancelSearch(jobId: string): Promise<Job> {
  return request<Job>(`/api/search/${jobId}/cancel`, { method: "POST" });
}

export function csvUrl(jobId: string, kind: "leads" | "evidence" = "leads"): string {
  return `${API_BASE}/api/export/csv?job_id=${encodeURIComponent(jobId)}&kind=${kind}`;
}

export function health(): Promise<{
  status: string;
  model: string;
  apify_configured: boolean;
  gemini_configured: boolean;
}> {
  return request("/api/health");
}

// --- Saved leads (§28) -----------------------------------------------------

export function saveLeads(
  jobId: string,
  leadIds: string[],
): Promise<SaveLeadsResult> {
  return request<SaveLeadsResult>("/api/saved-leads", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, lead_ids: leadIds }),
  });
}

export function listSavedLeads(limit = 200): Promise<SavedLeadsResponse> {
  return request<SavedLeadsResponse>(`/api/saved-leads?limit=${limit}`);
}

/** Which leads are already saved, so results can show them as ticked. */
export function savedLeadIds(): Promise<string[]> {
  return request<string[]>("/api/saved-leads/ids");
}

export function getSavedLead(leadId: string): Promise<SavedLead> {
  return request<SavedLead>(`/api/saved-leads/${leadId}`);
}

export async function deleteSavedLead(leadId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/saved-leads/${leadId}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new ApiError(await describeError(response), response.status);
}

// --- Follow-ups ------------------------------------------------------------

/** Download URL for every saved lead. A plain <a href>, not fetch: the browser
 *  handles the download from the Content-Disposition header. */
export function savedLeadsCsvUrl(): string {
  return `${API_BASE}/api/saved-leads/export/csv`;
}

export function listFollowUps(leadId: string): Promise<FollowUpsResponse> {
  return request<FollowUpsResponse>(`/api/saved-leads/${leadId}/followups`);
}

export function addFollowUp(leadId: string, body: FollowUpBody): Promise<FollowUp> {
  return request<FollowUp>(`/api/saved-leads/${leadId}/followups`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteFollowUp(leadId: string, followUpId: number): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/saved-leads/${leadId}/followups/${followUpId}`,
    { method: "DELETE" },
  );
  if (!response.ok) throw new ApiError(await describeError(response), response.status);
}

// --- Dashboard -------------------------------------------------------------

export function getDashboard(): Promise<Dashboard> {
  return request<Dashboard>("/api/dashboard");
}

// --- Manual lead entry -----------------------------------------------------

export function manualLeadOptions(): Promise<ManualLeadOptions> {
  return request<ManualLeadOptions>("/api/saved-leads/options");
}

export function createManualLead(body: ManualLeadBody): Promise<SavedLead> {
  return request<SavedLead>("/api/saved-leads/manual", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
