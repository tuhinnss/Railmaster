import { useMemo, useState } from "react";
import { DEPARTMENT_COLORS, REAL_DATA_COLOR } from "../constants/colors";
import type { Department, SectionPlanResult, TaskSummary } from "../types";

// Blocks occupy a few hundred metres each on a 300 km corridor, so a true-to-
// scale axis is ~99% empty and renders every block as a sliver. This view
// breaks the axis instead: stretches of corridor that carry work are drawn at a
// readable scale, and the empty stretches between them collapse into a marked
// break showing how much distance was skipped.
const ZOOM_LEVELS = [120, 260, 520]; // px per km *within* a worked stretch
const ZOOM_LABELS: Record<number, string> = { 120: "Compact", 260: "Normal", 520: "Wide" };
const GAP_PX = 56;
const MIN_GROUP_PX = 132;
const GAP_MIN_KM = 0.75; // shorter than this and it isn't worth breaking the axis
const LANE_HEIGHT = 22;
const LANE_GAP = 4;

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

export function corridorLabel(chain: SectionPlanResult[]): string {
  return `${chain[0].section.split("-")[0]} → ${chain[chain.length - 1].section.split("-")[1]}`;
}

export function groupIntoCorridors(sections: SectionPlanResult[]): SectionPlanResult[][] {
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

type Run =
  | { kind: "work"; kmFrom: number; kmTo: number; blocks: PositionedBlock[]; section: string; width: number }
  | { kind: "gap"; kmFrom: number; kmTo: number; section: string; width: number };

/** Cluster blocks into worked stretches, then fill the space between them with
 *  explicit gap runs. Gaps are split at section boundaries so every run belongs
 *  to exactly one section and the section band above stays accurate. */
function buildRuns(chain: SectionPlanResult[], pxPerKm: number): Run[] {
  const kmStart = Math.min(...chain.map((s) => s.km_start));
  const kmEnd = Math.max(...chain.map((s) => s.km_end));
  const blocks = chain.flatMap(positionBlocks).sort((a, b) => a.kmFrom - b.kmFrom);

  const clusters: { kmFrom: number; kmTo: number; blocks: PositionedBlock[] }[] = [];
  for (const block of blocks) {
    const last = clusters[clusters.length - 1];
    if (last && block.kmFrom <= last.kmTo + GAP_MIN_KM) {
      last.kmTo = Math.max(last.kmTo, block.kmTo);
      last.blocks.push(block);
    } else {
      clusters.push({ kmFrom: block.kmFrom, kmTo: block.kmTo, blocks: [block] });
    }
  }

  const sectionAt = (km: number) =>
    chain.find((s) => km >= s.km_start && km < s.km_end)?.section ?? chain[chain.length - 1].section;

  // Boundaries that a gap must be split on, so no run straddles two sections.
  const boundaries = chain.map((s) => s.km_end).filter((km) => km > kmStart && km < kmEnd);

  const runs: Run[] = [];
  const pushGap = (from: number, to: number) => {
    if (to - from < GAP_MIN_KM) return;
    let cursor = from;
    for (const b of [...boundaries, to].sort((x, y) => x - y)) {
      if (b <= cursor || b > to) continue;
      runs.push({ kind: "gap", kmFrom: cursor, kmTo: b, section: sectionAt(cursor), width: GAP_PX });
      cursor = b;
    }
    if (cursor < to) runs.push({ kind: "gap", kmFrom: cursor, kmTo: to, section: sectionAt(cursor), width: GAP_PX });
  };

  let cursor = kmStart;
  for (const c of clusters) {
    pushGap(cursor, c.kmFrom);
    runs.push({
      kind: "work",
      kmFrom: c.kmFrom,
      kmTo: c.kmTo,
      blocks: c.blocks,
      section: sectionAt(c.kmFrom),
      width: Math.max((c.kmTo - c.kmFrom) * pxPerKm, MIN_GROUP_PX),
    });
    cursor = Math.max(cursor, c.kmTo);
  }
  pushGap(cursor, kmEnd);

  return runs;
}

function metres(kmFrom: number, kmTo: number): string {
  const m = (kmTo - kmFrom) * 1000;
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
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
  const runs = useMemo(() => buildRuns(chain, pxPerKm), [chain, pxPerKm]);
  const totalBlocks = chain.reduce((n, s) => n + s.blocks.length, 0);
  const maxLanes = Math.max(1, ...runs.map((r) => (r.kind === "work" ? r.blocks.length : 1)));
  const lanesHeight = maxLanes * (LANE_HEIGHT + LANE_GAP);
  const skipped = runs.filter((r) => r.kind === "gap").reduce((sum, r) => sum + (r.kmTo - r.kmFrom), 0);

  // Merge consecutive runs of the same section into one band cell.
  const bands: { section: string; width: number; ntes: boolean }[] = [];
  for (const run of runs) {
    const last = bands[bands.length - 1];
    const ntes = chain.find((s) => s.section === run.section)?.ntes_integrated ?? false;
    if (last && last.section === run.section) last.width += run.width;
    else bands.push({ section: run.section, width: run.width, ntes });
  }

  const label = corridorLabel(chain);

  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div style={{ fontSize: 13, fontWeight: 700 }}>{label}</div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>
          {totalBlocks} blocks · {skipped.toFixed(0)} km of empty corridor skipped
        </div>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 0 8px" }}>
        <div style={{ display: "inline-flex", flexDirection: "column", minWidth: "100%" }}>
          {/* Section bands */}
          <div style={{ display: "flex", height: 24 }}>
            {bands.map((b, i) => (
              <div
                key={`${b.section}-${i}`}
                style={{
                  width: b.width,
                  flex: "0 0 auto",
                  background: b.ntes ? "#cffafe" : "#f1f5f9",
                  border: "1px solid",
                  borderColor: b.ntes ? REAL_DATA_COLOR : "#cbd5e1",
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
                {b.section}
              </div>
            ))}
          </div>

          {/* Blocks + gap breaks */}
          <div style={{ display: "flex", marginTop: 8, alignItems: "flex-start" }}>
            {runs.map((run, i) => {
              if (run.kind === "gap") {
                return (
                  <div
                    key={`gap-${i}`}
                    title={`${(run.kmTo - run.kmFrom).toFixed(2)} km with no scheduled work — skipped`}
                    style={{
                      width: run.width,
                      flex: "0 0 auto",
                      height: lanesHeight,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#cbd5e1",
                      fontSize: 10,
                      borderLeft: "2px dotted #e2e8f0",
                      borderRight: "2px dotted #e2e8f0",
                    }}
                  >
                    <span style={{ fontSize: 13, lineHeight: 1 }}>⋯</span>
                    <span style={{ color: "#94a3b8", marginTop: 2 }}>
                      {(run.kmTo - run.kmFrom).toFixed(1)} km
                    </span>
                  </div>
                );
              }

              return (
                <div key={`work-${i}`} style={{ width: run.width, flex: "0 0 auto", padding: "0 3px", boxSizing: "border-box" }}>
                  <div style={{ height: lanesHeight }}>
                    {run.blocks.map((b) => (
                      <div
                        key={b.blockId}
                        onMouseEnter={(e) => onHover(b, e)}
                        onMouseMove={(e) => onHover(b, e)}
                        onMouseLeave={onLeave}
                        style={{
                          display: "flex",
                          height: LANE_HEIGHT,
                          marginBottom: LANE_GAP,
                          borderRadius: 3,
                          overflow: "hidden",
                          cursor: "pointer",
                          border: "1px solid #0f172a",
                          boxShadow: b.isRealData ? `0 0 0 2px ${REAL_DATA_COLOR}` : "none",
                          boxSizing: "border-box",
                        }}
                      >
                        {b.departments.map((d) => (
                          <div
                            key={d}
                            style={{
                              flex: 1,
                              background: DEPARTMENT_COLORS[d],
                              color: "white",
                              fontSize: 10,
                              fontWeight: 700,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {run.width > 110 ? d.slice(0, 3).toUpperCase() : ""}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>

                  {/* Marked endpoints + length */}
                  <div
                    style={{
                      borderTop: "2px solid #334155",
                      position: "relative",
                      height: 30,
                      marginTop: 2,
                    }}
                  >
                    <span style={{ position: "absolute", left: 0, top: 0, width: 1, height: 5, background: "#334155" }} />
                    <span style={{ position: "absolute", right: 0, top: 0, width: 1, height: 5, background: "#334155" }} />
                    <span style={{ position: "absolute", left: 0, top: 6, fontSize: 9.5, color: "#334155", fontWeight: 600 }}>
                      {run.kmFrom.toFixed(2)}
                    </span>
                    <span style={{ position: "absolute", right: 0, top: 6, fontSize: 9.5, color: "#334155", fontWeight: 600 }}>
                      {run.kmTo.toFixed(2)}
                    </span>
                    <span
                      style={{
                        position: "absolute",
                        top: 17,
                        left: 0,
                        right: 0,
                        textAlign: "center",
                        fontSize: 9.5,
                        color: "#94a3b8",
                      }}
                    >
                      {metres(run.kmFrom, run.kmTo)}
                      {run.blocks.length > 1 ? ` · ${run.blocks.length} blocks` : ""}
                    </span>
                  </div>
                </div>
              );
            })}
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
            ["Km block", `${block.kmFrom.toFixed(2)} – ${block.kmTo.toFixed(2)} (${metres(block.kmFrom, block.kmTo)})`],
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
      <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
        <span style={{ color: "#cbd5e1", fontSize: 13 }}>⋯</span>
        empty corridor, skipped
      </span>
      <span style={{ display: "flex", alignItems: "center", gap: 5, marginLeft: "auto" }}>
        <span style={{ width: 12, height: 12, background: "#cffafe", borderRadius: 3, border: `1px solid ${REAL_DATA_COLOR}` }} />
        real NTES data
      </span>
    </div>
  );
}

export default function CorridorMap({ sections }: { sections: SectionPlanResult[] }) {
  const [pxPerKm, setPxPerKm] = useState(260);
  const [hovered, setHovered] = useState<{ block: PositionedBlock; x: number; y: number } | null>(null);
  const chains = useMemo(() => groupIntoCorridors(sections), [sections]);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Block width</span>
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
        <span style={{ fontSize: 11, color: "#94a3b8" }}>hover a block for its timetable</span>
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
