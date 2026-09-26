import type { BlockType, Department, SeverityCode } from "../types";

// Mirrors DEFECT_TYPES in backend/app/datagen/reference_data.py, for
// What-if's picker. Report Defect doesn't use them: a report says what was
// found in the reporter's own words.
export const DEFECT_TYPES: Record<Department, string[]> = {
  Engineering: ["rail_fracture_risk", "ballast_deficiency", "track_geometry_defect", "joint_wear", "formation_failure"],
  TRD: ["ohe_wire_wear", "insulator_damage", "feeder_fault", "isolator_failure", "earthing_defect"],
  "S&T": ["signal_relay_fault", "point_machine_defect", "cable_fault", "interlocking_fault", "level_crossing_fault"],
};

// Each department's most common need in the generator's weights
// (BLOCK_TYPE_WEIGHTS_BY_DEPT) -- a starting value, not a rule.
export const DEFAULT_BLOCK_TYPE: Record<Department, BlockType> = {
  Engineering: "traffic",
  TRD: "power",
  "S&T": "traffic",
};

// Mirrors SEVERITY_BANDS and DUE_DAYS_BY_SEVERITY in backend/app/operations.py,
// which decides; this is only so the form can show the band while a score is
// picked. Both are prototype assumptions, not railway rules.
export const SEVERITY_BANDS: [lowest: number, band: SeverityCode][] = [
  [8, "A"],
  [4, "B"],
  [1, "C"],
];

export function severityFromScore(score: number): SeverityCode {
  return SEVERITY_BANDS.find(([lowest]) => score >= lowest)?.[1] ?? "C";
}

export const SEVERITY_BAND_TEXT: Record<SeverityCode, string> = {
  A: "safety-critical, due today",
  B: "major, due within 7 days",
  C: "minor, due within 30 days",
};
