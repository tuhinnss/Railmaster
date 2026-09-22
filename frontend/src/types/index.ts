// TODO: mirror backend Pydantic models (MaintenanceTask, BlockWindow,
// ScheduledBlock, BlockPlan) as they solidify.

export type Department =
  | "ENGINEERING"
  | "SIGNAL_TELECOM"
  | "TRACTION_DISTRIBUTION";

export type Severity = "CRITICAL" | "MAJOR" | "MINOR";

export type Horizon = "WEEKLY" | "MONTHLY";
