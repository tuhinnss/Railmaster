import { DEPARTMENT_COLORS } from "../constants/colors";
import type { Department } from "../types";

export default function DepartmentBadge({ department }: { department: Department }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 12,
        fontWeight: 600,
        color: DEPARTMENT_COLORS[department],
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: DEPARTMENT_COLORS[department],
          display: "inline-block",
        }}
      />
      {department}
    </span>
  );
}
