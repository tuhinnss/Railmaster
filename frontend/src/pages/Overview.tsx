import { useState } from "react";
import BlockActionsPanel from "../components/BlockActionsPanel";
import CorridorMap from "../components/CorridorMap";
import UnscheduledWork from "../components/UnscheduledWork";
import { usePlan } from "../context/PlanContext";
import { useBlockDecisions } from "../hooks/useBlockDecisions";
import type { SectionPlanResult } from "../types";
import { planDaysOf } from "../utils/blockDecisions";

// Local calendar day a block starts on, as YYYY-MM-DD -- the same "day a block
// runs" rule the Weekly Plan grid uses.
function dayKey(time: string | Date): string {
  const d = new Date(time);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function dayLabel(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

const toggleStyle = (active: boolean) => ({
  fontSize: 12,
  padding: "4px 11px",
  borderRadius: 5,
  cursor: "pointer",
  border: active ? "1px solid #0f172a" : "1px solid #cbd5e1",
  background: active ? "#0f172a" : "white",
  color: active ? "white" : "#475569",
});

// Block allocation for one section, either the whole week or a single day.
// The day list holds only days that actually have blocks, so a day with nothing
// scheduled can't be picked. It opens on today when the plan covers today;
// blocks are generated for the next operating week, so often it doesn't, and
// it opens on the first planned day instead.
function AllocationView({
  section,
  onSelect,
  selectedId,
}: {
  section: SectionPlanResult;
  onSelect: (blockId: string) => void;
  selectedId: string | null;
}) {
  const [mode, setMode] = useState<"daily" | "weekly">("weekly");
  const [pickedDay, setPickedDay] = useState<string | null>(null);

  const counts = new Map<string, number>();
  for (const b of section.blocks) counts.set(dayKey(b.start_time), (counts.get(dayKey(b.start_time)) ?? 0) + 1);
  const days = Array.from(counts.keys()).sort();
  const today = dayKey(new Date());
  const day = pickedDay && counts.has(pickedDay) ? pickedDay : counts.has(today) ? today : days[0];

  const shown =
    mode === "weekly" ? section : { ...section, blocks: section.blocks.filter((b) => dayKey(b.start_time) === day) };

  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <button onClick={() => setMode("daily")} style={toggleStyle(mode === "daily")}>
          Daily
        </button>
        <button onClick={() => setMode("weekly")} style={toggleStyle(mode === "weekly")}>
          Weekly
        </button>
        {mode === "daily" && days.length > 0 && (
          <select
            value={day}
            onChange={(e) => setPickedDay(e.target.value)}
            style={{ fontSize: 12, padding: "4px 6px", border: "1px solid #cbd5e1", borderRadius: 5, marginLeft: 4 }}
          >
            {days.map((d) => (
              <option key={d} value={d}>
                {d === today ? "Today, " : ""}
                {dayLabel(d)} · {counts.get(d)} block{counts.get(d) === 1 ? "" : "s"}
              </option>
            ))}
          </select>
        )}
        {mode === "daily" && !counts.has(today) && days.length > 0 && (
          <span style={{ fontSize: 11, color: "#94a3b8" }}>
            No blocks today — this week's plan runs {dayLabel(days[0])} to {dayLabel(days[days.length - 1])}
          </span>
        )}
      </div>
      <CorridorMap sections={[shown]} onSelect={(b) => onSelect(b.blockId)} selectedId={selectedId} />
    </>
  );
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: 8,
        padding: "16px 20px",
        minWidth: 180,
        flex: "1 1 180px",
      }}
    >
      <div style={{ fontSize: 12, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function Overview() {
  const { plan, loading, error, refresh } = usePlan();
  const [selected, setSelected] = useState<string | null>(null);
  // The block clicked on the map, open in the side panel for reschedule / delete.
  const [openBlock, setOpenBlock] = useState<string | null>(null);
  const ops = useBlockDecisions();

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  // One section at a time: the corridors differ too much (NDLS-GZB fits ~half
  // its backlog, the Assam pair nearly all of it) for a combined total to mean
  // anything. Defaults to the first section.
  const current = plan.sections.find((s) => s.section === selected) ?? plan.sections[0];
  const sections = current ? [current] : [];

  const totalTasks = sections.reduce((sum, s) => sum + s.task_count, 0);
  const totalScheduled = sections.reduce((sum, s) => sum + s.scheduled_count, 0);
  const totalBlocksOpened = sections.reduce((sum, s) => sum + s.blocks_opened, 0);
  const totalBlocksSaved = sections.reduce((sum, s) => sum + s.blocks_saved, 0);
  const downtimeHours = sections.reduce((sum, s) => {
    return (
      sum +
      s.blocks.reduce((bsum, b) => {
        const ms = new Date(b.end_time).getTime() - new Date(b.start_time).getTime();
        return bsum + ms / 3_600_000;
      }, 0)
    );
  }, 0);
  const scheduledPct = totalTasks > 0 ? Math.round((totalScheduled / totalTasks) * 100) : 0;
  const didNotFit = totalTasks - totalScheduled;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ fontSize: 20 }}>Overview — Weekly Plan {plan.start_date}</h1>
        <button onClick={refresh} style={{ fontSize: 12 }}>
          Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Section</span>
        {plan.sections.map((s) => ({
          key: s.section,
          label: `${s.section} · ${s.scheduled_count}/${s.task_count}`,
        })).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => {
              setSelected(key);
              setOpenBlock(null);
              ops.setMessage(null);
            }}
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
            {label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 16 }}>
        {/* Only what answers "how did this week's plan do": work placed, blocks it
            took, and how long the line is closed for it. */}
        <KpiCard
          label="Tasks scheduled"
          value={`${scheduledPct}%`}
          sub={`${totalScheduled} of ${totalTasks}${didNotFit > 0 ? ` · ${didNotFit} didn't fit` : ""}`}
        />
        <KpiCard
          label="Blocks this week"
          value={String(totalBlocksOpened)}
          sub={`${totalBlocksSaved} saved by merging`}
        />
        <KpiCard
          label="Track downtime"
          value={`${downtimeHours.toFixed(1)} h`}
          sub={`across ${totalBlocksOpened} blocks`}
        />
      </div>

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Block allocation</h2>
      <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 12px" }}>
        Each marker is a scheduled block, positioned along the corridor by the km range of the work
        assigned to it. Hover a block for its timetable; click it to reschedule or delete it.
      </p>
      {current && (
        <AllocationView
          section={current}
          selectedId={openBlock}
          onSelect={(id) => {
            setOpenBlock(id);
            ops.setMessage(null);
          }}
        />
      )}

      {current && (
        <UnscheduledWork
          section={current}
          planDays={planDaysOf(plan.sections)}
          added={ops.added}
          decisionOf={ops.decisionOf}
          busy={ops.busy}
          // The side panel shows the outcome of its own actions.
          message={openBlock ? null : ops.message}
          onAdd={(task, start, minutes) => ops.add(current, task, start, minutes)}
          onRemove={(blockId) => ops.removeAdded(current, blockId)}
        />
      )}

      {current && openBlock && (
        <BlockActionsPanel
          section={current}
          blockId={openBlock}
          addedFor={ops.addedOf.get(openBlock)?.for_task}
          decision={ops.decisionOf.get(openBlock)}
          planDays={planDaysOf(plan.sections)}
          busy={ops.busy}
          message={ops.message}
          onMove={(newStart, durationMin) => ops.decide(current, openBlock, "rescheduled", { newStart, durationMin })}
          onDelete={() => ops.decide(current, openBlock, "cancelled")}
          onUndo={() => ops.undo(current, openBlock)}
          onClose={() => {
            setOpenBlock(null);
            ops.setMessage(null);
          }}
        />
      )}
    </div>
  );
}
