import { useMemo, useState } from "react";
import DepartmentBadge from "../components/DepartmentBadge";
import SeverityBadge from "../components/SeverityBadge";
import TaskDetailPanel from "../components/TaskDetailPanel";
import { usePlan } from "../context/PlanContext";
import type { Department, SectionPlanResult, SeverityCode, TaskSummary } from "../types";

type SortKey = "priority_score" | "days_overdue";

export default function TaskQueue() {
  const { plan, loading, error } = usePlan();
  const [departmentFilter, setDepartmentFilter] = useState<Department | "ALL">("ALL");
  const [severityFilter, setSeverityFilter] = useState<SeverityCode | "ALL">("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("priority_score");
  const [selected, setSelected] = useState<{ task: TaskSummary; section: SectionPlanResult } | null>(null);

  const rows = useMemo(() => {
    if (!plan) return [];
    const all: { task: TaskSummary; section: SectionPlanResult }[] = [];
    for (const section of plan.sections) {
      for (const task of section.tasks) {
        if (departmentFilter !== "ALL" && task.department !== departmentFilter) continue;
        if (severityFilter !== "ALL" && task.severity_code !== severityFilter) continue;
        all.push({ task, section });
      }
    }
    all.sort((a, b) =>
      sortKey === "priority_score"
        ? b.task.priority_score - a.task.priority_score
        : b.task.days_overdue - a.task.days_overdue
    );
    return all;
  }, [plan, departmentFilter, severityFilter, sortKey]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load: {error}</p>;

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Task Queue</h1>

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
            <th style={{ padding: "6px 8px" }}>Section</th>
            <th style={{ padding: "6px 8px" }}>Severity</th>
            <th style={{ padding: "6px 8px" }}>Overdue</th>
            <th style={{ padding: "6px 8px" }}>Priority</th>
            <th style={{ padding: "6px 8px" }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ task, section }) => (
            <tr
              key={task.task_id}
              onClick={() => setSelected({ task, section })}
              style={{ borderTop: "1px solid #f1f5f9", fontSize: 13, cursor: "pointer" }}
            >
              <td style={{ padding: "8px" }}>{task.task_id}</td>
              <td style={{ padding: "8px" }}>
                <DepartmentBadge department={task.department} />
              </td>
              <td style={{ padding: "8px" }}>{task.section}</td>
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

      {selected && (
        <TaskDetailPanel task={selected.task} section={selected.section} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
