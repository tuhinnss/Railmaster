import { useMemo, useState } from "react";
import DepartmentBadge from "../components/DepartmentBadge";
import SeverityBadge from "../components/SeverityBadge";
import TaskDetailPanel from "../components/TaskDetailPanel";
import { usePlan } from "../context/PlanContext";
import type { Department, SeverityCode, TaskSummary } from "../types";

type SortKey = "priority_score" | "days_overdue";

export default function TaskQueue() {
  const { plan, loading, error } = usePlan();
  const [sectionKey, setSectionKey] = useState<string | null>(null);
  const [departmentFilter, setDepartmentFilter] = useState<Department | "ALL">("ALL");
  const [severityFilter, setSeverityFilter] = useState<SeverityCode | "ALL">("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("priority_score");
  const [selected, setSelected] = useState<TaskSummary | null>(null);

  // One section at a time, as on the Overview and Weekly Plan: each section's
  // backlog competes only for its own blocks, so a combined ranking would put
  // tasks side by side that never compete. Defaults to the first section.
  const current = plan?.sections.find((s) => s.section === sectionKey) ?? plan?.sections[0];

  const rows = useMemo(() => {
    if (!current) return [];
    const tasks = current.tasks.filter(
      (task) =>
        (departmentFilter === "ALL" || task.department === departmentFilter) &&
        (severityFilter === "ALL" || task.severity_code === severityFilter)
    );
    tasks.sort((a, b) =>
      sortKey === "priority_score" ? b.priority_score - a.priority_score : b.days_overdue - a.days_overdue
    );
    return tasks;
  }, [current, departmentFilter, severityFilter, sortKey]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load: {error}</p>;
  if (!plan) return null;

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Task Queue</h1>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Section</span>
        {plan.sections.map((s) => (
          <button
            key={s.section}
            onClick={() => {
              setSectionKey(s.section);
              setSelected(null);
            }}
            style={{
              fontSize: 12,
              padding: "4px 11px",
              borderRadius: 5,
              cursor: "pointer",
              border: s.section === current?.section ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: s.section === current?.section ? "#0f172a" : "white",
              color: s.section === current?.section ? "white" : "#475569",
            }}
          >
            {s.section} · {s.task_count} tasks
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 16, margin: "12px 0", fontSize: 13, alignItems: "center" }}>
        <label>
          Department:{" "}
          <select value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value as Department | "ALL")}>
            <option value="ALL">All</option>
            <option value="Engineering">Engineering</option>
            <option value="TRD">TRD</option>
            <option value="S&T">S&T</option>
          </select>
        </label>
        <label>
          Severity:{" "}
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value as SeverityCode | "ALL")}>
            <option value="ALL">All</option>
            <option value="A">A</option>
            <option value="B">B</option>
            <option value="C">C</option>
          </select>
        </label>
        <label>
          Sort by:{" "}
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
            <option value="priority_score">Priority score</option>
            <option value="days_overdue">Days overdue</option>
          </select>
        </label>
        <span style={{ color: "#94a3b8" }}>{rows.length} tasks</span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", fontSize: 12, color: "#64748b" }}>
            <th style={{ padding: "6px 8px" }}>Task</th>
            <th style={{ padding: "6px 8px" }}>Department</th>
            <th style={{ padding: "6px 8px" }}>Severity</th>
            <th style={{ padding: "6px 8px" }}>Overdue</th>
            <th style={{ padding: "6px 8px" }}>Priority</th>
            <th style={{ padding: "6px 8px" }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((task) => (
            <tr
              key={task.task_id}
              onClick={() => setSelected(task)}
              style={{ borderTop: "1px solid #f1f5f9", fontSize: 13, cursor: "pointer" }}
            >
              <td style={{ padding: "8px" }}>{task.task_id}</td>
              <td style={{ padding: "8px" }}>
                <DepartmentBadge department={task.department} />
              </td>
              <td style={{ padding: "8px" }}>
                <SeverityBadge severity={task.severity_code} />
              </td>
              <td style={{ padding: "8px" }}>{task.days_overdue > 0 ? `${task.days_overdue}d` : "—"}</td>
              <td style={{ padding: "8px" }}>{task.priority_score.toFixed(2)}</td>
              <td style={{ padding: "8px" }}>
                {task.scheduled ? (
                  <span style={{ color: "#059669" }}>Scheduled</span>
                ) : (
                  <span style={{ color: "#dc2626" }}>Unscheduled</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && current && (
        <TaskDetailPanel task={selected} section={current} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
