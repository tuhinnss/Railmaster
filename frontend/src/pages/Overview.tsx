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

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  const totalTasks = plan.sections.reduce((sum, s) => sum + s.task_count, 0);
  const totalScheduled = plan.sections.reduce((sum, s) => sum + s.scheduled_count, 0);
  const totalOverdue = plan.sections.reduce(
    (sum, s) => sum + s.tasks.filter((t) => t.days_overdue > 0).length,
    0
  );
  const totalBlocksOpened = plan.sections.reduce((sum, s) => sum + s.blocks_opened, 0);
  const totalBlocksSaved = plan.sections.reduce((sum, s) => sum + s.blocks_saved, 0);
  const downtimeHours = plan.sections.reduce((sum, s) => {
    return (
      sum +
      s.blocks.reduce((bsum, b) => {
        const ms = new Date(b.end_time).getTime() - new Date(b.start_time).getTime();
        return bsum + ms / 3_600_000;
      }, 0)
    );
  }, 0);
  const availabilityPct = totalTasks > 0 ? Math.round((totalScheduled / totalTasks) * 100) : 0;
  const realDataBlocks = plan.sections.reduce(
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
        <KpiCard label="Overdue tasks" value={String(totalOverdue)} sub="across all sections" />
        <KpiCard
          label="Blocks using real data"
          value={String(realDataBlocks)}
          sub="from ntes-adapter (GHY-LMG, LMG-RNY)"
        />
      </div>

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
          {plan.sections.map((s) => (
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
