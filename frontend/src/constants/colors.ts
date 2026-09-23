// Department colors must stay visually distinct from severity colors --
// a merged block shows both at once (department chips inside a block
// that itself might carry a severity-driven task), so the two scales
// use entirely separate hue families.

import type { Department, SeverityCode } from "../types";

export const DEPARTMENT_COLORS: Record<Department, string> = {
  Engineering: "#2563eb", // blue
  TRD: "#d97706", // amber
  "S&T": "#059669", // emerald
};

export const SEVERITY_COLORS: Record<SeverityCode, string> = {
  A: "#dc2626", // red
  B: "#7c3aed", // violet
  C: "#64748b", // slate
};

export const SEVERITY_LABELS: Record<SeverityCode, string> = {
  A: "A — Safety-critical",
  B: "B — Major",
  C: "C — Minor",
};
