// Mirrors backend/app/schemas/plan.py and the /api/defects, /api/corridors
// response shapes exactly.

export type Department = "Engineering" | "TRD" | "S&T";

export type SeverityCode = "A" | "B" | "C";

export type BlockType = "traffic" | "power" | "traffic_and_power";

export type Horizon = "WEEKLY";

export type DataSource = "synthetic" | "ntes_live";

export interface TaskSummary {
  task_id: string;
  department: Department;
  section: string;
  defect_type: string;
  severity_code: SeverityCode;
  days_overdue: number;
  block_type_required: BlockType;
  priority_score: number;
  criticality: number;
  urgency: number;
  availability_impact: number;
  dominant_component: string;
  safety_override: boolean;
  scheduled: boolean;
  block_id: string | null;
  reason: string;
}

export interface ScheduledBlockSummary {
  block_id: string;
  section: string;
  start_time: string;
  end_time: string;
  block_type_possible: BlockType;
  task_ids: string[];
  data_source: DataSource;
}

export interface SectionPlanResult {
  section: string;
  task_count: number;
  scheduled_count: number;
  blocks_opened: number;
  blocks_used_without_merging: number;
  blocks_saved: number;
  tasks: TaskSummary[];
  blocks: ScheduledBlockSummary[];
}

export interface PlanResponse {
  horizon: Horizon;
  start_date: string;
  generated_at: string;
  sections: SectionPlanResult[];
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
