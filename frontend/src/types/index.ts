// Mirrors backend/app/schemas/plan.py and the /api/defects, /api/corridors
// response shapes exactly.

export type Department = "Engineering" | "TRD" | "S&T";

export type SeverityCode = "A" | "B" | "C";

export type BlockType = "traffic" | "power" | "traffic_and_power";

export type Horizon = "WEEKLY";

export type DataSource = "synthetic" | "ntes_live";

// "reported" = entered on the Report Defect page, not the generated backlog.
export type TaskSource = "synthetic" | "reported";

export interface TaskSummary {
  task_id: string;
  department: Department;
  section: string;
  km_range: [number, number];
  defect_type: string;
  severity_code: SeverityCode;
  days_overdue: number;
  block_type_required: BlockType;
  est_duration_min: number;
  priority_score: number;
  criticality: number;
  urgency: number;
  availability_impact: number;
  dominant_component: string;
  safety_override: boolean;
  scheduled: boolean;
  block_id: string | null;
  reason: string;
  data_source: TaskSource;
}

export interface ScheduledBlockSummary {
  block_id: string;
  section: string;
  start_time: string;
  end_time: string;
  block_type_possible: BlockType;
  task_ids: string[];
  data_source: DataSource;
  duration_min: number;
  used_min: number;
}

export interface SafetyCheck {
  rule: string;
  label: string;
  description: string;
  items_checked: number;
  violations: number;
  method: "inspected" | "structural";
}

export interface SectionPlanResult {
  section: string;
  km_start: number;
  km_end: number;
  ntes_integrated: boolean;
  task_count: number;
  scheduled_count: number;
  blocks_opened: number;
  blocks_used_without_merging: number;
  blocks_saved: number;
  tasks: TaskSummary[];
  blocks: ScheduledBlockSummary[];
  safety_checks: SafetyCheck[];
  fingerprint: string; // this section alone
}

export interface PlanResponse {
  horizon: Horizon;
  start_date: string;
  generated_at: string;
  fingerprint: string;
  sections: SectionPlanResult[];
}

// What-if replanning: POST /api/plans/WEEKLY/what-if
export type Disruption =
  | { kind: "cancel_block"; block_id: string }
  | { kind: "curtail_block"; block_id: string; minutes_lost: number }
  | { kind: "move_block"; block_id: string; new_start: string; duration_min?: number }
  | {
      kind: "urgent_defect";
      section: string;
      department: Department;
      defect_type: string;
      km_from: number;
      km_to: number;
      severity_code?: SeverityCode;
      est_duration_min: number;
      block_type_required: BlockType;
    };

export type TaskChangeKind = "dropped" | "added" | "moved" | "new_scheduled" | "new_unscheduled";

export interface TaskChange {
  task_id: string;
  section: string;
  change: TaskChangeKind;
  block_before: string | null;
  block_after: string | null;
  reason_after: string;
}

export interface WhatIfResponse {
  applied: string[];
  sections: { section: string; before: SectionPlanResult; after: SectionPlanResult }[];
  changes: TaskChange[];
  replan_seconds: number;
}

// Field reports and control decisions: /api/operations (backend/app/schemas/operations.py).
export interface DefectReportRequest {
  section: string;
  department: Department;
  defect_type: string;
  km_from: number;
  km_to: number;
  severity_code: SeverityCode;
  est_duration_min: number;
  block_type_required: BlockType;
  description: string;
  reported_by: string;
}

export interface DefectReport extends DefectReportRequest {
  report_id: string; // also the task_id it is planned under
  reported_at: string;
}

export type BlockDecisionKind = "granted" | "granted_late" | "rescheduled" | "cancelled";

export interface BlockDecision {
  block_id: string;
  section: string;
  planned_start: string;
  planned_end: string;
  decision: BlockDecisionKind;
  minutes_lost: number;
  decided_at: string;
  new_start: string | null; // set only when rescheduled
  new_end: string | null;
}

// Mirrors ntes-adapter's models.py, proxied through /api/corridors/{section}/trains.
export type TrainEventType = "arrival" | "departure";

export type TrainEventStatus = "on_time" | "delayed" | "source" | "terminating" | "unknown";

export interface TrainEvent {
  train_no: string;
  train_name: string;
  station_code: string;
  event_type: TrainEventType;
  status: TrainEventStatus;
  scheduled_time: string | null;
  actual_or_expected_time: string | null;
  delay_minutes: number | null;
  platform: string | null;
}

export interface StationLiveBoard {
  station_code: string;
  fetched_at: string;
  window_hours: number;
  events: TrainEvent[];
}

export interface LiveCorridorStatus {
  corridor: string;
  station_a: StationLiveBoard | null;
  station_b: StationLiveBoard | null;
  stale: boolean;
  last_successful_fetch: string | null;
  provider: string;
}

export interface CorridorBlock {
  block_id: string;
  section: string;
  start_time: string;
  end_time: string;
  duration_min: number;
  block_type_possible: BlockType;
  expected_train_impact: number;
  goods_traffic_load: number;
  data_source: DataSource;
}
