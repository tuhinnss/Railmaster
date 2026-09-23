import { SEVERITY_COLORS } from "../constants/colors";
import type { SeverityCode } from "../types";

export default function SeverityBadge({ severity }: { severity: SeverityCode }) {
  const color = SEVERITY_COLORS[severity];
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 700,
        color: "white",
        background: color,
        borderRadius: 4,
        padding: "2px 6px",
        display: "inline-block",
      }}
    >
      {severity}
    </span>
  );
}
