import { useMemo, useState } from "react";
import { DEPARTMENT_COLORS, REAL_DATA_COLOR } from "../constants/colors";
import type { Department, SectionPlanResult, TaskSummary } from "../types";

const ZOOM_LEVELS = [8, 20, 50]; // px per km
const ZOOM_LABELS: Record<number, string> = { 8: "Whole corridor", 20: "Closer", 50: "Detail" };
const MIN_BLOCK_PX = 12;
const LANE_HEIGHT = 18;
const LANE_GAP = 3;
const BAND_HEIGHT = 26;

export interface PositionedBlock {
  blockId: string;
  section: string;
  kmFrom: number;
  kmTo: number;
  departments: Department[];
  taskCount: number;
  tasks: TaskSummary[];
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
        section: section.section,
        kmFrom: Math.min(...tasks.map((t) => t.km_range[0])),
        kmTo: Math.max(...tasks.map((t) => t.km_range[1])),
        departments: Array.from(new Set(tasks.map((t) => t.department))),
        taskCount: tasks.length,
        tasks,
        isRealData: block.data_source === "ntes_live",
        startTime: block.start_time,
        endTime: block.end_time,
      },
    ];
  });
}

// Sections are contiguous by km within a corridor, but the dataset may hold
// several corridors that each restart their own km numbering. Grouping by
// overlapping km ranges would merge them into one nonsensical line, so they're
// chained on the station code the section name ends/starts with.
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

interface LaidOutBlock extends PositionedBlock {
  left: number;
  width: number;
  lane: number;
}

/** Blocks are tiny next to a 300 km corridor and several can sit at nearly the
 *  same km on different nights, so drawing them in one row buries them on top
 *  of each other. Pack them into stacked lanes instead: each block keeps a
 *  minimum clickable width and drops to the first lane where it doesn't
 *  collide. */
function layOutBlocks(blocks: PositionedBlock[], kmStart: number, pxPerKm: number): LaidOutBlock[] {
  const sorted = [...blocks].sort((a, b) => a.kmFrom - b.kmFrom);
  const laneEnds: number[] = [];
  const out: LaidOutBlock[] = [];

  for (const block of sorted) {
    const left = (block.kmFrom - kmStart) * pxPerKm;
    const width = Math.max((block.kmTo - block.kmFrom) * pxPerKm, MIN_BLOCK_PX);

    let lane = laneEnds.findIndex((end) => left >= end + 2);
    if (lane === -1) lane = laneEnds.length;
    laneEnds[lane] = left + width;

    out.push({ ...block, left, width, lane });
  }
  return out;
}

function tickInterval(pxPerKm: number): number {
  if (pxPerKm >= 50) return 2;
  if (pxPerKm >= 20) return 5;
  return 20;
}

function CorridorLine({
  chain,
  pxPerKm,
  onHover,
  onLeave,
}: {
  chain: SectionPlanResult[];
  pxPerKm: number;
  onHover: (block: PositionedBlock, e: React.MouseEvent) => void;
  onLeave: () => void;
}) {
  const kmStart = Math.min(...chain.map((s) => s.km_start));
  const kmEnd = Math.max(...chain.map((s) => s.km_end));
  const width = (kmEnd - kmStart) * pxPerKm;

  const blocks = chain.flatMap(positionBlocks);
  const laidOut = layOutBlocks(blocks, kmStart, pxPerKm);
  const laneCount = Math.max(1, ...laidOut.map((b) => b.lane + 1));
  const lanesHeight = laneCount * (LANE_HEIGHT + LANE_GAP);

  const step = tickInterval(pxPerKm);
  const firstTick = Math.ceil(kmStart / step) * step;
  const ticks: number[] = [];
  for (let km = firstTick; km <= kmEnd; km += step) ticks.push(km);

  const label = `${chain[0].section.split("-")[0]} → ${chain[chain.length - 1].section.split("-")[1]}`;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>{label}</div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>
          {kmStart}–{kmEnd} km · {blocks.length} blocks
        </div>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 0 6px" }}>
        <div style={{ width, minWidth: "100%", position: "relative", paddingLeft: 1 }}>
          {/* Section bands */}
          <div style={{ display: "flex", height: BAND_HEIGHT }}>
            {chain.map((s) => (
              <div
                key={s.section}
                style={{
                  width: (s.km_end - s.km_start) * pxPerKm,
                  background: s.ntes_integrated ? "#cffafe" : "#f1f5f9",
                  border: "1px solid",
                  borderColor: s.ntes_integrated ? REAL_DATA_COLOR : "#cbd5e1",
                  boxSizing: "border-box",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#334155",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                }}
              >
                {s.section} · km {s.km_start}–{s.km_end}
                {s.ntes_integrated ? " · real NTES data" : ""}
              </div>
            ))}
          </div>

          {/* Block lanes */}
          <div style={{ position: "relative", height: lanesHeight, marginTop: 6 }}>
            {ticks.map((km) => (
              <div
                key={`grid-${km}`}
                style={{
                  position: "absolute",
                  left: (km - kmStart) * pxPerKm,
                  top: 0,
                  bottom: 0,
                  borderLeft: "1px dashed #f1f5f9",
                }}
              />
            ))}

            {laidOut.map((b) => (
              <div
                key={b.blockId}
                onMouseEnter={(e) => onHover(b, e)}
                onMouseMove={(e) => onHover(b, e)}
                onMouseLeave={onLeave}
                style={{
                  position: "absolute",
                  left: b.left,
                  width: b.width,
                  top: b.lane * (LANE_HEIGHT + LANE_GAP),
                  height: LANE_HEIGHT,
                  display: "flex",
                  borderRadius: 3,
                  overflow: "hidden",
                  cursor: "pointer",
                  border: "1px solid #0f172a",
                  boxShadow: b.isRealData ? `0 0 0 2px ${REAL_DATA_COLOR}` : "none",
                  boxSizing: "border-box",
                }}
              >
                {b.departments.map((d) => (
                  <div key={d} style={{ flex: 1, background: DEPARTMENT_COLORS[d] }} />
                ))}
              </div>
            ))}
          </div>

          {/* km axis */}
          <div style={{ position: "relative", height: 16, borderTop: "1px solid #e2e8f0", marginTop: 4 }}>
            {ticks.map((km) => (
              <span
                key={km}
                style={{
                  position: "absolute",
                  left: (km - kmStart) * pxPerKm,
                  fontSize: 9,
                  color: "#94a3b8",
                  transform: "translateX(-50%)",
                  paddingTop: 2,
                }}
              >
                {km}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function HoverCard({ block, x, y }: { block: PositionedBlock; x: number; y: number }) {
  const start = new Date(block.startTime);
  const end = new Date(block.endTime);
  const durationMin = Math.round((end.getTime() - start.getTime()) / 60000);
  const hhmm = (d: Date) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  // Keep the card on screen near the right edge.
  const flip = x > window.innerWidth - 300;

  return (
    <div
      style={{
        position: "fixed",
        left: flip ? x - 290 : x + 14,
        top: Math.min(y + 14, window.innerHeight - 220),
        width: 276,
        background: "white",
        border: "1px solid #cbd5e1",
        borderRadius: 8,
        boxShadow: "0 8px 24px rgba(15,23,42,0.16)",
        padding: 12,
        zIndex: 100,
        pointerEvents: "none",
        fontSize: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontWeight: 700 }}>{block.blockId}</span>
        {block.isRealData && (
          <span style={{ fontSize: 9, fontWeight: 700, color: "white", background: REAL_DATA_COLOR, borderRadius: 3, padding: "1px 5px" }}>
            REAL NTES
          </span>
        )}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <tbody>
          {[
            ["Date", start.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short", year: "numeric" })],
            ["Time", `${hhmm(start)} – ${hhmm(end)} (${durationMin} min)`],
            ["Km block", `${block.kmFrom.toFixed(2)} – ${block.kmTo.toFixed(2)} (${((block.kmTo - block.kmFrom) * 1000).toFixed(0)} m)`],
            ["Section", block.section],
          ].map(([k, v]) => (
            <tr key={k}>
              <td style={{ color: "#94a3b8", padding: "2px 8px 2px 0", verticalAlign: "top", whiteSpace: "nowrap" }}>{k}</td>
              <td style={{ padding: "2px 0" }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ borderTop: "1px solid #f1f5f9", marginTop: 8, paddingTop: 6 }}>
        <div style={{ color: "#94a3b8", marginBottom: 4 }}>
          {block.taskCount} task{block.taskCount === 1 ? "" : "s"}
          {block.taskCount > 1 ? " merged into this block" : ""}
        </div>
        {block.tasks.map((t) => (
          <div key={t.task_id} style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: DEPARTMENT_COLORS[t.department], flex: "0 0 auto" }} />
            <span style={{ fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {t.department} — {t.defect_type.replaceAll("_", " ")}
            </span>
          </div>
        ))}
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
      }}
    >
      <span style={{ fontWeight: 700, fontSize: 11, textTransform: "uppercase", color: "#64748b" }}>
        Departments
      </span>
      {Object.entries(DEPARTMENT_COLORS).map(([dept, color]) => (
        <span key={dept} style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 12, height: 12, background: color, borderRadius: 3, border: "1px solid #0f172a" }} />
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
  const [pxPerKm, setPxPerKm] = useState(20);
  const [hovered, setHovered] = useState<{ block: PositionedBlock; x: number; y: number } | null>(null);
  const chains = useMemo(() => groupIntoCorridors(sections), [sections]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Zoom</span>
        {ZOOM_LEVELS.map((z) => (
          <button
            key={z}
            onClick={() => setPxPerKm(z)}
            style={{
              fontSize: 12,
              padding: "3px 10px",
              borderRadius: 5,
              cursor: "pointer",
              border: z === pxPerKm ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: z === pxPerKm ? "#0f172a" : "white",
              color: z === pxPerKm ? "white" : "#475569",
            }}
          >
            {ZOOM_LABELS[z]}
          </button>
        ))}
        <span style={{ fontSize: 11, color: "#94a3b8" }}>scroll sideways · hover a block for its timetable</span>
      </div>

      <div style={{ marginBottom: 14 }}>
        <DepartmentLegend />
      </div>

      {chains.map((chain) => (
        <CorridorLine
          key={chain[0].section}
          chain={chain}
          pxPerKm={pxPerKm}
          onHover={(block, e) => setHovered({ block, x: e.clientX, y: e.clientY })}
          onLeave={() => setHovered(null)}
        />
      ))}

      {hovered && <HoverCard block={hovered.block} x={hovered.x} y={hovered.y} />}
    </div>
  );
}
