// Client for the FastAPI backend (spec §26).
//
// No API keys live here. The browser only ever talks to our own backend, which
// holds the Apify and Gemini credentials server-side (§37).

import type {
  Job,
  LeadsResponse,
  SearchBody,
  SessionDetail,
  SessionListResponse,
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
    // fetch() only rejects on network-level failure, which here almost always
    // means the backend is not running.
    throw new ApiError(
      `Cannot reach the API at ${API_BASE}. Is the backend running?`,
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

// --- Saved sessions (§28) --------------------------------------------------

export function saveSession(
  jobId: string,
  name?: string,
): Promise<SessionDetail> {
  return request<SessionDetail>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, name: name ?? null }),
  });
}

export function listSessions(limit = 50): Promise<SessionListResponse> {
  return request<SessionListResponse>(`/api/sessions?limit=${limit}`);
}

export function getSession(id: number): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/sessions/${id}`);
}

export function renameSession(id: number, name: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/sessions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ job_id: "", name }),
  });
}

export async function deleteSession(id: number): Promise<void> {
  const response = await fetch(`${API_BASE}/api/sessions/${id}`, { method: "DELETE" });
  if (!response.ok) throw new ApiError(await describeError(response), response.status);
}
