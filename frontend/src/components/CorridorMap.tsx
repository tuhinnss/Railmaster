import { DEPARTMENT_COLORS, REAL_DATA_COLOR } from "../constants/colors";
import type { Department, SectionPlanResult, TaskSummary } from "../types";

// Sections are contiguous by km within a corridor, but the dataset holds two
// separate corridors that each restart their own km numbering. Grouping by
// overlapping km ranges would merge them into one nonsensical line, so they're
// split on the station code the section name ends/starts with.
function groupIntoCorridors(sections: SectionPlanResult[]): SectionPlanResult[][] {
  const remaining = [...sections].sort((a, b) => a.km_start - b.km_start);
  const chains: SectionPlanResult[][] = [];

  while (remaining.length > 0) {
    const chain = [remaining.shift()!];
    let extended = true;
    while (extended) {
      extended = false;
      const tail = chain[chain.length - 1].section.split("-")[1];
      const head = chain[0].section.split("-")[0];
      const nextIdx = remaining.findIndex((s) => s.section.split("-")[0] === tail);
      if (nextIdx >= 0) {
        chain.push(remaining.splice(nextIdx, 1)[0]);
        extended = true;
        continue;
      }
      const prevIdx = remaining.findIndex((s) => s.section.split("-")[1] === head);
      if (prevIdx >= 0) {
        chain.unshift(remaining.splice(prevIdx, 1)[0]);
        extended = true;
      }
    }
    chains.push(chain);
  }
  return chains;
}

export interface PositionedBlock {
  blockId: string;
  kmFrom: number;
  kmTo: number;
  departments: Department[];
  taskCount: number;
  isRealData: boolean;
  startTime: string;
  endTime: string;
}

// A block has no km range of its own -- it inherits the span of the work
// actually assigned to it, which is what "where is this block" means.
export function positionBlocks(section: SectionPlanResult): PositionedBlock[] {
  return section.blocks.flatMap((block) => {
    const tasks = block.task_ids
      .map((id) => section.tasks.find((t) => t.task_id === id))
      .filter((t): t is TaskSummary => Boolean(t));
    if (tasks.length === 0) return [];

    return [
      {
        blockId: block.block_id,
        kmFrom: Math.min(...tasks.map((t) => t.km_range[0])),
        kmTo: Math.max(...tasks.map((t) => t.km_range[1])),
        departments: Array.from(new Set(tasks.map((t) => t.department))),
        taskCount: tasks.length,
        isRealData: block.data_source === "ntes_live",
        startTime: block.start_time,
        endTime: block.end_time,
      },
    ];
  });
}

function CorridorLine({ chain }: { chain: SectionPlanResult[] }) {
  const kmStart = Math.min(...chain.map((s) => s.km_start));
  const kmEnd = Math.max(...chain.map((s) => s.km_end));
  const span = kmEnd - kmStart || 1;
  const pct = (km: number) => ((km - kmStart) / span) * 100;

  const label = `${chain[0].section.split("-")[0]} → ${chain[chain.length - 1].section.split("-")[1]}`;
  const totalBlocks = chain.reduce((sum, s) => sum + s.blocks.length, 0);

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>{label}</div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>
          {kmStart}–{kmEnd} km · {totalBlocks} blocks
        </div>
      </div>

      {/* Section bands */}
      <div style={{ position: "relative", height: 22, display: "flex", borderRadius: 4, overflow: "hidden" }}>
        {chain.map((s) => (
          <div
            key={s.section}
            title={`${s.section} — km ${s.km_start}–${s.km_end}, ${s.blocks.length} blocks${
              s.ntes_integrated ? " (real NTES data)" : ""
            }`}
            style={{
              width: `${((s.km_end - s.km_start) / span) * 100}%`,
              background: s.ntes_integrated ? "#cffafe" : "#f1f5f9",
              borderRight: "1px solid white",
              fontSize: 10,
              color: "#475569",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              whiteSpace: "nowrap",
              overflow: "hidden",
            }}
          >
            {s.section} · km {s.km_start}–{s.km_end}
          </div>
        ))}
      </div>

      {/* Block markers, positioned by the km span of their assigned work */}
      <div style={{ position: "relative", height: 34, marginTop: 3 }}>
        {chain.flatMap((section) =>
          positionBlocks(section).map((b) => {
            const left = pct(b.kmFrom);
            const width = Math.max(pct(b.kmTo) - left, 0.8);
            return (
              <div
                key={b.blockId}
                title={`${b.blockId}\nkm ${b.kmFrom}–${b.kmTo} on ${section.section}\n${
                  b.taskCount
                } task(s): ${b.departments.join(", ")}\n${new Date(b.startTime).toLocaleString()}${
                  b.isRealData ? "\nReal NTES data" : ""
                }`}
                style={{
                  position: "absolute",
                  left: `${left}%`,
                  width: `${width}%`,
                  top: 0,
                  height: 16,
                  display: "flex",
                  borderRadius: 3,
                  overflow: "hidden",
                  minWidth: 4,
                  boxShadow: b.isRealData ? `0 0 0 1.5px ${REAL_DATA_COLOR}` : "none",
                }}
              >
                {b.departments.map((d) => (
                  <div key={d} style={{ flex: 1, background: DEPARTMENT_COLORS[d] }} />
                ))}
              </div>
            );
          })
        )}
      </div>

      {/* km axis */}
      <div style={{ position: "relative", height: 14, borderTop: "1px solid #e2e8f0" }}>
        {chain.map((s) => (
          <span
            key={s.section}
            style={{ position: "absolute", left: `${pct(s.km_start)}%`, fontSize: 9, color: "#94a3b8" }}
          >
            {s.km_start}
          </span>
        ))}
        <span style={{ position: "absolute", right: 0, fontSize: 9, color: "#94a3b8" }}>{kmEnd}</span>
      </div>
    </div>
  );
}

export function DepartmentLegend() {
  return (
    <div
      style={{
        display: "flex",
        gap: 16,
        fontSize: 12,
        color: "#475569",
        flexWrap: "wrap",
        alignItems: "center",
        padding: "8px 12px",
        background: "#f8fafc",
        border: "1px solid #e2e8f0",
        borderRadius: 6,
        marginBottom: 14,
      }}
    >
      <span style={{ fontWeight: 700, fontSize: 11, textTransform: "uppercase", color: "#64748b" }}>
        Departments
      </span>
      {Object.entries(DEPARTMENT_COLORS).map(([dept, color]) => (
        <span key={dept} style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 12, height: 12, background: color, borderRadius: 3 }} />
          {dept}
        </span>
      ))}
      <span style={{ display: "flex", alignItems: "center", gap: 5, marginLeft: "auto" }}>
        <span style={{ width: 12, height: 12, background: "#cffafe", borderRadius: 3, border: `1px solid ${REAL_DATA_COLOR}` }} />
        real NTES data
      </span>
    </div>
  );
}

export default function CorridorMap({ sections }: { sections: SectionPlanResult[] }) {
  const chains = groupIntoCorridors(sections);

  return (
    <div>
      <DepartmentLegend />
      {chains.map((chain) => (
        <CorridorLine key={chain[0].section} chain={chain} />
      ))}
    </div>
  );
}
