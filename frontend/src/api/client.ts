import type {
  CorridorBlock,
  CorridorTrainPaths,
  Disruption,
  Horizon,
  LiveCorridorStatus,
  PlanResponse,
  TaskSummary,
  WhatIfResponse,
} from "../types";

const BASE_URL = "/api";

// FastAPI puts a human-readable reason in `detail` for the errors this app
// raises on purpose (unknown block, km outside the section, ...); surface
// it instead of a bare status code.
async function failure(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return new Error(body.detail);
  } catch {
    // not JSON -- fall through
  }
  return new Error(`Request failed: ${res.status}`);
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw await failure(res);
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await failure(res);
  return res.json();
}

export function fetchPlan(horizon: Horizon = "WEEKLY"): Promise<PlanResponse> {
  return apiGet<PlanResponse>(`/plans/${horizon}`);
}

export function runWhatIf(disruptions: Disruption[], horizon: Horizon = "WEEKLY"): Promise<WhatIfResponse> {
  return apiPost<WhatIfResponse>(`/plans/${horizon}/what-if`, { disruptions });
}

export function fetchDefects(): Promise<TaskSummary[]> {
  return apiGet<TaskSummary[]>("/defects/");
}

export function fetchCorridorBlocks(section?: string): Promise<CorridorBlock[]> {
  const qs = section ? `?section=${encodeURIComponent(section)}` : "";
  return apiGet<CorridorBlock[]>(`/corridors/${qs}`);
}

export function fetchCorridorTrains(section: string): Promise<LiveCorridorStatus> {
  return apiGet<LiveCorridorStatus>(`/corridors/${encodeURIComponent(section)}/trains`);
}

export function fetchTrainPaths(section: string): Promise<CorridorTrainPaths> {
  return apiGet<CorridorTrainPaths>(`/corridors/${encodeURIComponent(section)}/train-paths`);
}
