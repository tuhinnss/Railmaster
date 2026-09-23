import DepartmentBadge from "./DepartmentBadge";
import SeverityBadge from "./SeverityBadge";
import { DEPARTMENT_COLORS } from "../constants/colors";
import type { SectionPlanResult, TaskSummary } from "../types";

interface Props {
  task: TaskSummary;
  section: SectionPlanResult;
  onClose: () => void;
}

function ScoreBar({ label, value, weightLabel }: { label: string; value: number; weightLabel: string }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
        <span>
          {label} <span style={{ color: "#94a3b8" }}>({weightLabel})</span>
        </span>
        <span style={{ fontWeight: 600 }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ background: "#e2e8f0", borderRadius: 4, height: 6 }}>
        <div
          style={{
            width: `${Math.min(value, 1) * 100}%`,
            background: "#0f172a",
            height: 6,
            borderRadius: 4,
          }}
        />
      </div>
    </div>
  );
}

export default function TaskDetailPanel({ task, section, onClose }: Props) {
  const block = task.block_id ? section.blocks.find((b) => b.block_id === task.block_id) : null;
  const shareTaskIds = block ? block.task_ids.filter((id) => id !== task.task_id) : [];
  const shareTasks = shareTaskIds
    .map((id) => section.tasks.find((t) => t.task_id === id))
    .filter((t): t is TaskSummary => Boolean(t));

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: 380,
        background: "white",
        borderLeft: "1px solid #e2e8f0",
        boxShadow: "-4px 0 16px rgba(0,0,0,0.08)",
        padding: 20,
        overflowY: "auto",
        zIndex: 50,
      }}
    >
      <button onClick={onClose} style={{ float: "right", border: "none", background: "none", cursor: "pointer", fontSize: 16 }}>
        ✕
      </button>
      <div style={{ marginBottom: 4 }}>
        <DepartmentBadge department={task.department} />
      </div>
      <h2 style={{ fontSize: 16, margin: "4px 0" }}>{task.task_id}</h2>
      <div style={{ fontSize: 13, color: "#475569", marginBottom: 12 }}>
        {task.defect_type.replaceAll("_", " ")} · {task.section}
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
        <SeverityBadge severity={task.severity_code} />
        <span style={{ fontSize: 12, color: "#475569" }}>
          {task.days_overdue > 0 ? `${task.days_overdue} days overdue` : "not overdue"}
        </span>
        {task.safety_override && (
          <span style={{ fontSize: 11, fontWeight: 700, color: "#dc2626" }}>SAFETY OVERRIDE</span>
        )}
      </div>

      <h3 style={{ fontSize: 13, textTransform: "uppercase", color: "#64748b", marginBottom: 8 }}>
        Score breakdown — total {task.priority_score.toFixed(2)}
      </h3>
      <ScoreBar label="Criticality" value={task.criticality} weightLabel="w=0.5" />
      <ScoreBar label="Urgency" value={task.urgency} weightLabel="w=0.3" />
      <ScoreBar label="Availability impact" value={task.availability_impact} weightLabel="w=0.2" />
      <div style={{ fontSize: 12, color: "#475569", marginBottom: 16 }}>
        Driven mainly by <strong>{task.dominant_component.replaceAll("_", " ")}</strong>.
      </div>

      <h3 style={{ fontSize: 13, textTransform: "uppercase", color: "#64748b", marginBottom: 8 }}>
        Outcome
      </h3>
      <p style={{ fontSize: 13, lineHeight: 1.5, marginBottom: 16 }}>{task.reason}</p>

      {block && (
        <>
          <h3 style={{ fontSize: 13, textTransform: "uppercase", color: "#64748b", marginBottom: 8 }}>
            Block {block.block_id}
          </h3>
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            {new Date(block.start_time).toLocaleString()} → {new Date(block.end_time).toLocaleTimeString()}
            <br />
            Type: {block.block_type_possible}
          </div>
          {shareTasks.length > 0 && (
            <>
              <div style={{ fontSize: 12, color: "#64748b", marginBottom: 6 }}>
                Shares this block with {shareTasks.length} other task(s):
              </div>
              <ul style={{ paddingLeft: 18, fontSize: 12 }}>
                {shareTasks.map((t) => (
                  <li key={t.task_id} style={{ marginBottom: 4 }}>
                    <span style={{ color: DEPARTMENT_COLORS[t.department] }}>{t.department}</span> — {t.task_id}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
