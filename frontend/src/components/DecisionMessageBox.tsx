import type { DecisionMessage } from "../hooks/useBlockDecisions";

// The outcome of a control-office decision: what was done, then every task
// the re-optimised plan moved because of it.
export default function DecisionMessageBox({ message }: { message: DecisionMessage }) {
  return (
    <div
      style={{
        border: `1px solid ${message.error ? "#fca5a5" : "#cbd5e1"}`,
        background: message.error ? "#fef2f2" : "#f8fafc",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 13,
        marginBottom: 14,
      }}
    >
      <strong>{message.head}</strong>
      {!message.error &&
        (message.lines.length === 0 ? (
          <div style={{ color: "#64748b", marginTop: 3 }}>No task changed block.</div>
        ) : (
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {message.lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ))}
    </div>
  );
}
