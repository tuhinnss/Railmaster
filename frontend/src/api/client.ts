import type { CorridorBlock, Horizon, PlanResponse, TaskSummary } from "../types";

const BASE_URL = "/api";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

export function fetchPlan(horizon: Horizon = "WEEKLY"): Promise<PlanResponse> {
  return apiGet<PlanResponse>(`/plans/${horizon}`);
}

export function fetchDefects(): Promise<TaskSummary[]> {
  return apiGet<TaskSummary[]>("/defects/");
}

export function fetchCorridorBlocks(section?: string): Promise<CorridorBlock[]> {
  const qs = section ? `?section=${encodeURIComponent(section)}` : "";
  return apiGet<CorridorBlock[]>(`/corridors/${qs}`);
}
