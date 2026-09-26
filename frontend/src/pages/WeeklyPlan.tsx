import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import RealDataBadge from "../components/RealDataBadge";
import SafetyChecks from "../components/SafetyChecks";
import SeverityBadge from "../components/SeverityBadge";
import TaskDetailPanel from "../components/TaskDetailPanel";
import { BLOCK_TYPE_LABELS, DEPARTMENT_COLORS } from "../constants/colors";
import { usePlan } from "../context/PlanContext";
import type { Department, ScheduledBlockSummary, SectionPlanResult, TaskSummary } from "../types";
import { hhmm } from "../utils/time";

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

// Columns come from the blocks themselves, not plan.start_date: blocks are
// generated for the next operating week, which usually starts days after
// the plan's reference date (the old Gantt clipped blocks by assuming
// otherwise -- see commit de3be0c).
function planDays(sections: SectionPlanResult[]): number[] {
  const starts = sections.flatMap((s) => s.blocks.map((b) => startOfDay(new Date(b.start_time))));
  if (starts.length === 0) return [];
  const first = Math.min(...starts);
  const last = Math.max(...starts);
  return Array.from({ length: Math.round((last - first) / DAY_MS) + 1 }, (_, i) => first + i * DAY_MS);
}

function tasksOf(block: ScheduledBlockSummary, section: SectionPlanResult): TaskSummary[] {
  return block.task_ids
    .map((id) => section.tasks.find((t) => t.task_id === id))
    .filter((t): t is TaskSummary => Boolean(t));
}

export function DeptKey({ department }: { department: Department }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, marginRight: 8, whiteSpace: "nowrap" }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: DEPARTMENT_COLORS[department] }} />
      {department}
    </span>
  );
}

function CapacityBar({ used, total }: { used: number; total: number }) {
  return (
    <div title={`${used} of ${total} min used by assigned work`}>
      <div style={{ background: "#e2e8f0", borderRadius: 2, height: 4, marginTop: 5 }}>
        <div style={{ width: `${Math.min(100, (used / total) * 100)}%`, background: "#334155", height: 4, borderRadius: 2 }} />
      </div>
      <div style={{ fontSize: 10, color: "#64748b", marginTop: 2 }}>
        {used}/{total} min used
      </div>
    </div>
  );
}

function BlockCard({
  block,
  section,
  selected,
  onSelect,
}: {
  block: ScheduledBlockSummary;
  section: SectionPlanResult;
  selected: boolean;
  onSelect: () => void;
}) {
  const tasks = tasksOf(block, section);
  const departments = Array.from(new Set(tasks.map((t) => t.department)));
  const edge = selected ? "#0f172a" : "#e2e8f0";

  return (
    <button
      onClick={onSelect}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        background: selected ? "#f1f5f9" : "white",
        // One value per property: mixing a border shorthand with a side
        // longhand makes React warn and mis-update when `selected` toggles.
        borderStyle: "solid",
        borderWidth: "1px 1px 1px 4px",
        borderColor: `${edge} ${edge} ${edge} ${DEPARTMENT_COLORS[departments[0]]}`,
        borderRadius: 5,
        padding: "5px 7px",
        marginBottom: 6,
        cursor: "pointer",
        font: "inherit",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, fontWeight: 700 }}>
          {hhmm(block.start_time)}–{hhmm(block.end_time)}
        </span>
        {block.data_source === "ntes_live" && <RealDataBadge compact />}
      </div>
      <div style={{ fontSize: 10.5, color: "#64748b" }}>{BLOCK_TYPE_LABELS[block.block_type_possible]}</div>
      <div style={{ fontSize: 10.5, color: "#334155", marginTop: 3, display: "flex", flexWrap: "wrap" }}>
        {departments.map((d) => (
          <DeptKey key={d} department={d} />
        ))}
      </div>
      {tasks.length > 1 && (
        <div style={{ fontSize: 10.5, fontWeight: 600, color: "#0f172a", marginTop: 2 }}>{tasks.length} tasks merged</div>
      )}
      <CapacityBar used={block.used_min} total={block.duration_min} />
    </button>
  );
}

function BlockDetail({
  block,
  section,
  onSelectTask,
  onClose,
}: {
  block: ScheduledBlockSummary;
  section: SectionPlanResult;
  onSelectTask: (task: TaskSummary) => void;
  onClose: () => void;
}) {
  const tasks = tasksOf(block, section);
  const start = new Date(block.start_time);

  return (
    <div style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: 14, marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <span style={{ fontSize: 14, fontWeight: 700 }}>{block.block_id}</span>{" "}
          <span style={{ fontSize: 12, color: "#64748b" }}>
            {section.section} ·{" "}
            {start.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })},{" "}
            {hhmm(block.start_time)}–{hhmm(block.end_time)} · {BLOCK_TYPE_LABELS[block.block_type_possible]} block
          </span>
        </div>
        <button onClick={onClose} style={{ border: "none", background: "none", cursor: "pointer", fontSize: 14 }}>
          ✕
        </button>
      </div>
      {block.data_source === "ntes_live" && (
        <div style={{ marginTop: 6 }}>
          <RealDataBadge />
        </div>
      )}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 10 }}>
        <thead>
          <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
            <th style={{ padding: "4px 6px", fontWeight: 600 }}>Task</th>
            <th style={{ padding: "4px 6px", fontWeight: 600 }}>Department</th>
            <th style={{ padding: "4px 6px", fontWeight: 600 }}>Defect</th>
            <th style={{ padding: "4px 6px", fontWeight: 600 }}>Km</th>
            <th style={{ padding: "4px 6px", fontWeight: 600 }}>Severity</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr
              key={t.task_id}
              onClick={() => onSelectTask(t)}
              style={{ borderTop: "1px solid #f1f5f9", cursor: "pointer" }}
              title="Open the task's score breakdown"
            >
              <td style={{ padding: "5px 6px", fontWeight: 600 }}>{t.task_id}</td>
              <td style={{ padding: "5px 6px" }}>
                <DeptKey department={t.department} />
              </td>
              <td style={{ padding: "5px 6px" }}>{t.defect_type.replaceAll("_", " ")}</td>
              <td style={{ padding: "5px 6px", whiteSpace: "nowrap" }}>
                {t.km_range[0].toFixed(2)}–{t.km_range[1].toFixed(2)}
              </td>
              <td style={{ padding: "5px 6px" }}>
                <SeverityBadge severity={t.severity_code} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <CapacityBar used={block.used_min} total={block.duration_min} />
    </div>
  );
}

export default function WeeklyPlan() {
  const { plan, loading, error } = usePlan();
  const [selected, setSelected] = useState<string | null>(null);
  const [openBlock, setOpenBlock] = useState<{ blockId: string; section: string } | null>(null);
  const [selectedTask, setSelectedTask] = useState<{ task: TaskSummary; section: SectionPlanResult } | null>(null);

  const days = useMemo(() => (plan ? planDays(plan.sections) : []), [plan]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  // One section at a time, as on the Overview. Defaults to the first section.
  const current = plan.sections.find((s) => s.section === selected) ?? plan.sections[0];
  const sections = current ? [current] : [];
  // A block opened on another section stays closed when you switch away from it.
  const openSection = openBlock && openBlock.section === current?.section ? current : undefined;
  const openBlockData = openSection?.blocks.find((b) => b.block_id === openBlock?.blockId);
  const unscheduled = sections.flatMap((s) => s.tasks.filter((t) => !t.scheduled).map((t) => ({ t, s })));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ fontSize: 20 }}>
          Weekly Plan
          {days.length > 0 && (
            <span style={{ fontWeight: 400, color: "#64748b" }}>
              {" "}
              — {new Date(days[0]).toLocaleDateString(undefined, { day: "numeric", month: "short" })} to{" "}
              {new Date(days[days.length - 1]).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
            </span>
          )}
        </h1>
        <Link
          to={current ? `/print?section=${encodeURIComponent(current.section)}` : "/print"}
          target="_blank"
          style={{ fontSize: 12 }}
        >
          Printable version ↗
        </Link>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Section</span>
        {plan.sections.map((s) => s.section).map((key) => (
          <button
            key={key}
            onClick={() => setSelected(key)}
            style={{
              fontSize: 12,
              padding: "4px 11px",
              borderRadius: 5,
              cursor: "pointer",
              border: key === current?.section ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: key === current?.section ? "#0f172a" : "white",
              color: key === current?.section ? "white" : "#475569",
            }}
          >
            {key}
          </button>
        ))}
      </div>

      <p style={{ fontSize: 12, color: "#64748b", margin: "12px 0 8px" }}>
        Each card is one block, filed under the calendar day it starts. The left edge shows the first
        department using it; the bar shows how much of the block's length the assigned work uses. Click a
        card for its tasks.
      </p>

      <div style={{ overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 8 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `112px repeat(${days.length}, minmax(122px, 1fr))`,
            minWidth: 112 + days.length * 122,
          }}
        >
          <div style={{ borderBottom: "1px solid #e2e8f0" }} />
          {days.map((d) => (
            <div
              key={d}
              style={{
                fontSize: 11.5,
                fontWeight: 700,
                color: "#334155",
                padding: "8px 8px 6px",
                borderBottom: "1px solid #e2e8f0",
                borderLeft: "1px solid #f1f5f9",
              }}
            >
              {new Date(d).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
            </div>
          ))}

          {sections.map((s) => (
            <div key={s.section} style={{ display: "contents" }}>
              <div style={{ padding: "8px", borderBottom: "1px solid #f1f5f9" }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>{s.section}</div>
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                  {s.scheduled_count}/{s.task_count} tasks
                  <br />
                  {s.blocks_opened} blocks
                </div>
              </div>
              {days.map((d) => (
                <div
                  key={d}
                  style={{ padding: "6px", borderBottom: "1px solid #f1f5f9", borderLeft: "1px solid #f1f5f9" }}
                >
                  {s.blocks
                    .filter((b) => startOfDay(new Date(b.start_time)) === d)
                    .map((b) => (
                      <BlockCard
                        key={b.block_id}
                        block={b}
                        section={s}
                        selected={openBlock?.blockId === b.block_id}
                        onSelect={() => setOpenBlock({ blockId: b.block_id, section: s.section })}
                      />
                    ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {openSection && openBlockData && (
        <BlockDetail
          block={openBlockData}
          section={openSection}
          onSelectTask={(task) => setSelectedTask({ task, section: openSection })}
          onClose={() => setOpenBlock(null)}
        />
      )}

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Not scheduled this week ({unscheduled.length})</h2>
      {unscheduled.length === 0 ? (
        <p style={{ fontSize: 13, color: "#64748b" }}>Every task in scope has a block.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Task</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Section</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Needs</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Why it did not fit</th>
            </tr>
          </thead>
          <tbody>
            {unscheduled.map(({ t, s }) => (
              <tr
                key={t.task_id}
                onClick={() => setSelectedTask({ task: t, section: s })}
                style={{ borderTop: "1px solid #f1f5f9", cursor: "pointer" }}
              >
                <td style={{ padding: "6px", whiteSpace: "nowrap" }}>
                  <div style={{ fontWeight: 600 }}>{t.task_id}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 2 }}>
                    <SeverityBadge severity={t.severity_code} />
                    {t.safety_override && <span style={{ fontSize: 10, fontWeight: 700, color: "#dc2626" }}>OVERRIDE</span>}
                  </div>
                </td>
                <td style={{ padding: "6px" }}>{s.section}</td>
                <td style={{ padding: "6px", whiteSpace: "nowrap" }}>{t.est_duration_min} min · {BLOCK_TYPE_LABELS[t.block_type_required]}</td>
                <td style={{ padding: "6px", color: "#475569" }}>{t.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Safety checks</h2>
      <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 10px" }}>
        The validator re-checks every rule against the solver's output, independently of the constraints the
        solver was given. A plan with any violation is never shown — the API refuses it.
      </p>
      {sections.map((s) => (
        <details key={s.section} style={{ marginBottom: 8 }}>
          <summary style={{ fontSize: 13, cursor: "pointer" }}>
            <strong>{s.section}</strong>{" "}
            <span style={{ color: "#64748b" }}>
              — {s.safety_checks.filter((c) => c.violations === 0).length}/{s.safety_checks.length} rules hold
            </span>
          </summary>
          <div style={{ padding: "6px 0 0 16px" }}>
            <SafetyChecks checks={s.safety_checks} />
          </div>
        </details>
      ))}

      {selectedTask && (
        <TaskDetailPanel task={selectedTask.task} section={selectedTask.section} onClose={() => setSelectedTask(null)} />
      )}
    </div>
  );
}
