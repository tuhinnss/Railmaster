import type { BlockType, Department } from "../types";

// Mirrors DEFECT_TYPES in backend/app/datagen/reference_data.py. The backend
// rejects a report whose defect type isn't its department's, so keep in step.
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
