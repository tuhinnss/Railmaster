import { useState } from "react";
import MagnifiedPlan, { planTimeRange } from "../components/MagnifiedPlan";
import RealDataBadge from "../components/RealDataBadge";
import TaskDetailPanel from "../components/TaskDetailPanel";
import { DEPARTMENT_COLORS, REAL_DATA_COLOR } from "../constants/colors";
import { usePlan } from "../context/PlanContext";
import type { ScheduledBlockSummary, SectionPlanResult, TaskSummary } from "../types";

const DAY_MS = 24 * 60 * 60 * 1000;

function BlockBar({
  block,
  section,
  rangeStart,
  rangeMs,
  onSelectTask,
}: {
  block: ScheduledBlockSummary;
  section: SectionPlanResult;
  rangeStart: number;
  rangeMs: number;
  onSelectTask: (task: TaskSummary) => void;
}) {
  const start = new Date(block.start_time).getTime();
  const end = new Date(block.end_time).getTime();
  const leftPct = Math.max(0, ((start - rangeStart) / rangeMs) * 100);
  const widthPct = Math.max(0.6, ((end - start) / rangeMs) * 100);

  const tasks = block.task_ids
    .map((id) => section.tasks.find((t) => t.task_id === id))
    .filter((t): t is TaskSummary => Boolean(t));
  const departments = Array.from(new Set(tasks.map((t) => t.department)));
  const isMerged = tasks.length > 1;
  const isRealData = block.data_source === "ntes_live";

  return (
    <div
      title={`${block.block_id} — ${tasks.length} task(s)\n${new Date(block.start_time).toLocaleString()}${
        isRealData ? "\nUses real NTES-derived data" : ""
      }`}
      onClick={() => tasks[0] && onSelectTask(tasks[0])}
      style={{
        position: "absolute",
        left: `${leftPct}%`,
        width: `${widthPct}%`,
        top: 4,
        bottom: 4,
        display: "flex",
        borderRadius: 4,
        overflow: "hidden",
        cursor: "pointer",
        boxShadow: isMerged ? "0 0 0 2px #0f172a" : isRealData ? `0 0 0 2px ${REAL_DATA_COLOR}` : "none",
        minWidth: 6,
      }}
    >
      {departments.map((dept) => (
        <div key={dept} style={{ flex: 1, background: DEPARTMENT_COLORS[dept] }} />
      ))}
      {isRealData && (
        <div style={{ position: "absolute", top: 2, right: 2 }}>
          <RealDataBadge compact />
        </div>
      )}
    </div>
  );
}

export default function WeeklyPlan() {
  const { plan, loading, error } = usePlan();
  const [selected, setSelected] = useState<{ task: TaskSummary; section: SectionPlanResult } | null>(null);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load: {error}</p>;
  if (!plan) return null;

  // Blocks are generated for the next operating week, which does not start on
  // plan.start_date -- deriving the axis from the blocks themselves stops the
  // later days being positioned past 100% and rendered off-screen.
  const range = planTimeRange(plan.sections);
  const rangeStart = range ? range.start : new Date(plan.start_date + "T00:00:00").getTime();
  const rangeEnd = range ? range.end : rangeStart + 7 * DAY_MS;
  const rangeMs = rangeEnd - rangeStart;
  const dayCount = Math.round(rangeMs / DAY_MS);
  const dayLabels = Array.from({ length: dayCount }, (_, i) => {
    const d = new Date(rangeStart + i * DAY_MS);
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  });

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Weekly Plan — {plan.start_date}</h1>
      <div style={{ display: "flex", gap: 16, fontSize: 12, margin: "10px 0", color: "#475569" }}>
        {Object.entries(DEPARTMENT_COLORS).map(([dept, color]) => (
          <span key={dept} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ width: 10, height: 10, background: color, display: "inline-block", borderRadius: 2 }} />
            {dept}
          </span>
        ))}
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, border: "2px solid #0f172a", display: "inline-block", borderRadius: 2 }} />
          merged block (multiple tasks)
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <RealDataBadge compact />
          real NTES data (GHY-LMG, LMG-RNY)
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", fontSize: 11, color: "#94a3b8" }}>
        <div />
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${dayCount}, 1fr)` }}>
          {dayLabels.map((label) => (
            <div key={label} style={{ borderLeft: "1px solid #f1f5f9", paddingLeft: 4 }}>
              {label}
            </div>
          ))}
        </div>
      </div>

      {plan.sections.map((section) => (
        <div key={section.section} style={{ display: "grid", gridTemplateColumns: "120px 1fr", marginTop: 6 }}>
          <div style={{ fontSize: 13, fontWeight: 600, alignSelf: "center" }}>{section.section}</div>
          <div
            style={{
              position: "relative",
              height: 36,
              background: `repeating-linear-gradient(90deg, #f8fafc, #f8fafc calc(100%/${dayCount} - 1px), #f1f5f9 calc(100%/${dayCount}))`,
              borderRadius: 4,
            }}
          >
            {section.blocks.map((block) => (
              <BlockBar
                key={block.block_id}
                block={block}
                section={section}
                rangeStart={rangeStart}
                rangeMs={rangeMs}
                onSelectTask={(task) => setSelected({ task, section })}
              />
            ))}
          </div>
        </div>
      ))}

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Detailed schedule</h2>
      <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 10px" }}>
        Every block to scale, with its time, date and department. Scroll sideways for the full plan;
        shaded bands are the 00:00–05:00 night window.
      </p>
      <MagnifiedPlan
        sections={plan.sections}
        onSelectTask={(task, section) => setSelected({ task, section })}
      />

      {selected && (
        <TaskDetailPanel task={selected.task} section={selected.section} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
