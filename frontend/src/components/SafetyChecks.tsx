import type { SafetyCheck } from "../types";

// The validator's six spec-section-6 rules, run against solver output. A
// rule that examined nothing passed vacuously, and says so rather than
// showing the same tick as a rule that inspected twenty assignments.
function outcome(check: SafetyCheck): { text: string; color: string } {
  if (check.violations > 0) return { text: `${check.violations} violation(s)`, color: "#dc2626" };
  if (check.method === "structural") return { text: "holds by construction", color: "#475569" };
  if (check.items_checked === 0) return { text: "nothing to check", color: "#94a3b8" };
  return { text: `passed · ${check.items_checked} checked`, color: "#15803d" };
}

export default function SafetyChecks({ checks }: { checks: SafetyCheck[] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <thead>
        <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
          <th style={{ padding: "4px 6px", fontWeight: 600 }}>Rule</th>
          <th style={{ padding: "4px 6px", fontWeight: 600 }}>What is checked</th>
          <th style={{ padding: "4px 6px", fontWeight: 600 }}>Result</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((c) => {
          const o = outcome(c);
          return (
            <tr key={c.rule} style={{ borderTop: "1px solid #f1f5f9" }}>
              <td style={{ padding: "5px 6px", fontWeight: 600, whiteSpace: "nowrap" }}>{c.label}</td>
              <td style={{ padding: "5px 6px", color: "#475569" }}>{c.description}</td>
              <td style={{ padding: "5px 6px", whiteSpace: "nowrap", color: o.color, fontWeight: 600 }}>
                {c.violations > 0 ? "✕ " : "✓ "}
                {o.text}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
