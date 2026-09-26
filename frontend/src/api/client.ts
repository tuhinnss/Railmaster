import type {
  AddedBlock,
  BlockDecision,
  BlockDecisionKind,
  CorridorBlock,
  DefectReport,
  DefectReportRequest,
  Disruption,
  Horizon,
  LiveCorridorStatus,
  PlanResponse,
  QuietSlots,
  TaskSummary,
  TimetableCheck,
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

async function send<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await failure(res);
  return res.json();
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return send<T>("POST", path, body);
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return send<T>("PUT", path, body);
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "DELETE" });
  if (!res.ok) throw await failure(res);
}

export function fetchPlan(horizon: Horizon = "WEEKLY"): Promise<PlanResponse> {
  return apiGet<PlanResponse>(`/plans/${horizon}`);
}

export function runWhatIf(disruptions: Disruption[], horizon: Horizon = "WEEKLY"): Promise<WhatIfResponse> {
  return apiPost<WhatIfResponse>(`/plans/${horizon}/what-if`, { disruptions });
}

export function fetchReports(): Promise<DefectReport[]> {
  return apiGet<DefectReport[]>("/operations/reports");
}

export function submitReport(report: DefectReportRequest): Promise<DefectReport> {
  return apiPost<DefectReport>("/operations/reports", report);
}

export function withdrawReport(reportId: string): Promise<void> {
  return apiDelete(`/operations/reports/${encodeURIComponent(reportId)}`);
}

export function fetchDecisions(): Promise<BlockDecision[]> {
  return apiGet<BlockDecision[]>("/operations/decisions");
}

// newStart is local wall-clock time, "YYYY-MM-DDTHH:MM" with no zone -- the
// same naive local time every block in the plan is expressed in.
export function decideBlock(
  blockId: string,
  decision: BlockDecisionKind,
  opts: { minutesLost?: number; newStart?: string; durationMin?: number } = {}
): Promise<BlockDecision> {
  return apiPut<BlockDecision>(`/operations/decisions/${encodeURIComponent(blockId)}`, {
    decision,
    minutes_lost: opts.minutesLost ?? 0,
    new_start: opts.newStart ?? null,
    duration_min: opts.durationMin ?? null,
  });
}

export function undoDecision(blockId: string): Promise<void> {
  return apiDelete(`/operations/decisions/${encodeURIComponent(blockId)}`);
}

export function fetchAddedBlocks(): Promise<AddedBlock[]> {
  return apiGet<AddedBlock[]>("/operations/added-blocks");
}

// start is local wall-clock time with no zone, like decideBlock's newStart.
export function addBlock(taskId: string, start: string, durationMin: number): Promise<AddedBlock> {
  return apiPost<AddedBlock>("/operations/added-blocks", { task_id: taskId, start, duration_min: durationMin });
}

export function removeAddedBlock(blockId: string): Promise<void> {
  return apiDelete(`/operations/added-blocks/${encodeURIComponent(blockId)}`);
}

export function fetchDefects(): Promise<TaskSummary[]> {
  return apiGet<TaskSummary[]>("/defects/");
}

export function fetchCorridorBlocks(section?: string): Promise<CorridorBlock[]> {
  const qs = section ? `?section=${encodeURIComponent(section)}` : "";
  return apiGet<CorridorBlock[]>(`/corridors/${qs}`);
}

export function fetchTimetableCheck(
  section: string,
  kmFrom: number,
  kmTo: number,
  start: string,
  durationMin: number
): Promise<TimetableCheck> {
  const qs = new URLSearchParams({ km_from: String(kmFrom), km_to: String(kmTo), start, duration_min: String(durationMin) });
  return apiGet<TimetableCheck>(`/corridors/${encodeURIComponent(section)}/timetable-check?${qs}`);
}

export function fetchQuietSlots(
  section: string,
  kmFrom: number,
  kmTo: number,
  day: string,
  durationMin: number,
  around: string
): Promise<QuietSlots> {
  const qs = new URLSearchParams({ km_from: String(kmFrom), km_to: String(kmTo), day, duration_min: String(durationMin), around });
  return apiGet<QuietSlots>(`/corridors/${encodeURIComponent(section)}/quiet-slots?${qs}`);
}

export function fetchCorridorTrains(section: string): Promise<LiveCorridorStatus> {
  return apiGet<LiveCorridorStatus>(`/corridors/${encodeURIComponent(section)}/trains`);
}
