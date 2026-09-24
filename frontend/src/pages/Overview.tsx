import { useMemo, useState } from "react";
import BlockAllocation from "../components/BlockAllocation";
import CorridorMap, { corridorLabel, groupIntoCorridors } from "../components/CorridorMap";
import { usePlan } from "../context/PlanContext";

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
  const [corridor, setCorridor] = useState<string>("ALL");

  const chains = useMemo(() => (plan ? groupIntoCorridors(plan.sections) : []), [plan]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  const selectedChain = chains.find((c) => corridorLabel(c) === corridor);
  const sections = selectedChain ?? plan.sections;

  const totalTasks = sections.reduce((sum, s) => sum + s.task_count, 0);
  const totalScheduled = sections.reduce((sum, s) => sum + s.scheduled_count, 0);
  const totalOverdue = sections.reduce(
    (sum, s) => sum + s.tasks.filter((t) => t.days_overdue > 0).length,
    0
  );
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
  const availabilityPct = totalTasks > 0 ? Math.round((totalScheduled / totalTasks) * 100) : 0;
  const realDataBlocks = sections.reduce(
    (sum, s) => sum + s.blocks.filter((b) => b.data_source === "ntes_live").length,
    0
  );

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 style={{ fontSize: 20 }}>Overview — Weekly Plan {plan.start_date}</h1>
        <button onClick={refresh} style={{ fontSize: 12 }}>
          Refresh
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Corridor</span>
        {[{ key: "ALL", label: `All corridors (${plan.sections.length} sections)` }].concat(
          chains.map((c) => ({ key: corridorLabel(c), label: corridorLabel(c) }))
        ).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setCorridor(key)}
            style={{
              fontSize: 12,
              padding: "4px 11px",
              borderRadius: 5,
              cursor: "pointer",
              border: key === corridor ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: key === corridor ? "#0f172a" : "white",
              color: key === corridor ? "white" : "#475569",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 16 }}>
        <KpiCard
          label="Tasks addressed this week"
          value={`${availabilityPct}%`}
          sub={`${totalScheduled} / ${totalTasks} tasks`}
        />
        <KpiCard
          label="Corridor downtime hours"
          value={downtimeHours.toFixed(1)}
          sub={`across ${totalBlocksOpened} blocks`}
        />
        <KpiCard label="Blocks this week" value={String(totalBlocksOpened)} sub={`${totalBlocksSaved} saved via merging`} />
        <KpiCard
          label="Tasks that did not fit"
          value={String(totalTasks - totalScheduled)}
          sub={totalTasks - totalScheduled > 0 ? "no compatible window available" : "everything scheduled"}
        />
        <KpiCard label="Overdue tasks" value={String(totalOverdue)} sub={`of ${totalTasks} in scope`} />
        <KpiCard
          label="Blocks using real data"
          value={String(realDataBlocks)}
          sub={`of ${totalBlocksOpened}, from ntes-adapter`}
        />
      </div>

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Where the work lands</h2>
      <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 12px" }}>
        Each marker is a scheduled block, positioned along the corridor by the km range of the work
        assigned to it.
      </p>
      <CorridorMap sections={sections} />

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Block allocation by day</h2>
      <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 12px" }}>
        Every scheduled block, grouped by the day it runs — km block, time allocated, and which
        department has it.
      </p>
      <BlockAllocation sections={sections} />

      <h2 style={{ fontSize: 15, marginTop: 28 }}>By section</h2>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
        <thead>
          <tr style={{ textAlign: "left", fontSize: 12, color: "#64748b" }}>
            <th style={{ padding: "6px 8px" }}>Section</th>
            <th style={{ padding: "6px 8px" }}>Scheduled</th>
            <th style={{ padding: "6px 8px" }}>Blocks opened</th>
            <th style={{ padding: "6px 8px" }}>Blocks saved</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((s) => (
            <tr key={s.section} style={{ borderTop: "1px solid #f1f5f9", fontSize: 13 }}>
              <td style={{ padding: "8px" }}>{s.section}</td>
              <td style={{ padding: "8px" }}>
                {s.scheduled_count} / {s.task_count}
              </td>
              <td style={{ padding: "8px" }}>{s.blocks_opened}</td>
              <td style={{ padding: "8px" }}>{s.blocks_saved}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
