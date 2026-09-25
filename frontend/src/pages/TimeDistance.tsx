import { useEffect, useMemo, useState } from "react";
import { fetchTrainPaths } from "../api/client";
import { positionBlocks, type PositionedBlock } from "../components/CorridorMap";
import ProvenanceBanner from "../components/ProvenanceBanner";
import { DEPARTMENT_COLORS } from "../constants/colors";
import { usePlan } from "../context/PlanContext";
import type { CorridorTrainPaths, SectionPlanResult, TrainPath } from "../types";
import { hhmm } from "../utils/time";

// A night runs from 20:00 to 10:00 next morning: wide enough for the
// generator's 22:00 and 00:00-05:00 block windows, and for the NDLS/GZB
// captures, which cover roughly 23:30 to 10:00.
const FRAME_START_MIN = 20 * 60;
const FRAME_MIN = 14 * 60;
// ntes-adapter's NIGHT_WINDOWS: the window its availability estimate is for.
const PREDICTED_WINDOW = { from: 1 * 60, to: 5 * 60 };

const W = 1040;
const H = 420;
const M = { top: 30, right: 16, bottom: 34, left: 74 };
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;
const INK = "#334155";
const GRID = "#e2e8f0";

// Minutes into the 20:00-10:00 frame. Time of day only: the captured
// boards' calendar dates are not the dates they were observed (see
// ProvenanceBanner), so a train is drawn at its clock time on any night.
function frameMinute(d: Date): number {
  return (d.getHours() * 60 + d.getMinutes() - FRAME_START_MIN + 1440) % 1440;
}

const x = (frameMin: number) => M.left + (frameMin / FRAME_MIN) * PLOT_W;

function nightKey(d: Date): number {
  // Anything before noon belongs to the night that started the evening before.
  const n = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  if (d.getHours() < 12) n.setDate(n.getDate() - 1);
  return n.getTime();
}

type Hover =
  | { kind: "block"; block: PositionedBlock; x: number; y: number }
  | { kind: "train"; path: TrainPath; x: number; y: number };

function Tooltip({ hover, section }: { hover: Hover; section: SectionPlanResult }) {
  const [a, b] = section.section.split("-");
  const flip = hover.x > window.innerWidth - 300;
  const rows: [string, string][] =
    hover.kind === "block"
      ? [
          ["Time", `${hhmm(new Date(hover.block.startTime))}–${hhmm(new Date(hover.block.endTime))}`],
          ["Km", `${hover.block.kmFrom.toFixed(2)}–${hover.block.kmTo.toFixed(2)}`],
          ["Work", hover.block.tasks.map((t) => `${t.department}: ${t.defect_type.replaceAll("_", " ")}`).join("; ")],
        ]
      : [
          ["Direction", hover.path.direction === "a_to_b" ? `${a} → ${b}` : `${b} → ${a}`],
          ["Departed", hhmm(new Date(hover.path.departed_at))],
          ["Arrived", hhmm(new Date(hover.path.arrived_at))],
          [
            "In section",
            `${Math.round((new Date(hover.path.arrived_at).getTime() - new Date(hover.path.departed_at).getTime()) / 60000)} min`,
          ],
        ];

  return (
    <div
      style={{
        position: "fixed",
        left: flip ? hover.x - 280 : hover.x + 14,
        top: Math.min(hover.y + 14, window.innerHeight - 170),
        width: 262,
        background: "white",
        border: "1px solid #cbd5e1",
        borderRadius: 8,
        boxShadow: "0 8px 24px rgba(15,23,42,0.16)",
        padding: 10,
        zIndex: 100,
        pointerEvents: "none",
        fontSize: 12,
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 4 }}>
        {hover.kind === "block" ? hover.block.blockId : `${hover.path.train_no} ${hover.path.train_name}`}
      </div>
      <table style={{ borderCollapse: "collapse" }}>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td style={{ color: "#94a3b8", padding: "1px 8px 1px 0", verticalAlign: "top" }}>{k}</td>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Chart({
  section,
  blocks,
  paths,
  onHover,
}: {
  section: SectionPlanResult;
  blocks: PositionedBlock[];
  paths: TrainPath[];
  onHover: (h: Hover | null) => void;
}) {
  const [a, b] = section.section.split("-");
  const span = section.km_end - section.km_start;
  const y = (km: number) => M.top + ((km - section.km_start) / span) * PLOT_H;
  const hours = Array.from({ length: FRAME_MIN / 60 + 1 }, (_, i) => i * 60);
  const kmStep = span > 100 ? 20 : span > 40 ? 10 : 5;
  const predictedFrom = (PREDICTED_WINDOW.from - FRAME_START_MIN + 1440) % 1440;
  const predictedLen = PREDICTED_WINDOW.to - PREDICTED_WINDOW.from;
  const kmTicks = Array.from({ length: Math.floor(span / kmStep) + 1 }, (_, i) => section.km_start + i * kmStep);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} role="img"
      aria-label={`Time-distance chart for ${section.section}: planned blocks and paired train movements`}>
      {/* The window ntes-adapter estimates availability for. */}
      <rect x={x(predictedFrom)} y={M.top} width={x(predictedFrom + predictedLen) - x(predictedFrom)}
        height={PLOT_H} fill="#f1f5f9" />
      <text x={x(predictedFrom) + 4} y={M.top - 8} fontSize={10} fill="#64748b">
        01:00–05:00 · the window ntes-adapter estimates availability for
      </text>

      {/* Hour grid */}
      {hours.map((m) => {
        const clock = (FRAME_START_MIN + m) % 1440;
        const midnight = clock === 0;
        return (
          <g key={m}>
            <line x1={x(m)} x2={x(m)} y1={M.top} y2={M.top + PLOT_H} stroke={midnight ? "#94a3b8" : GRID} strokeWidth={1} />
            <text x={x(m)} y={H - M.bottom + 16} fontSize={10.5} fill={midnight ? INK : "#64748b"} textAnchor="middle"
              fontWeight={midnight ? 700 : 400}>
              {String(Math.floor(clock / 60)).padStart(2, "0")}:00
            </text>
          </g>
        );
      })}

      {/* Km axis, with the two stations at its ends */}
      {kmTicks.map((km) => (
        <g key={km}>
          <line x1={M.left} x2={M.left + PLOT_W} y1={y(km)} y2={y(km)} stroke={GRID} strokeWidth={1} />
          <text x={M.left - 8} y={y(km) + 3.5} fontSize={10} fill="#64748b" textAnchor="end">
            km {km}
          </text>
        </g>
      ))}
      <text x={6} y={y(section.km_start) + 4} fontSize={12} fontWeight={700} fill={INK}>{a}</text>
      <text x={6} y={y(section.km_end) + 4} fontSize={12} fontWeight={700} fill={INK}>{b}</text>

      {/* Planned blocks: a rectangle over the time the block runs and the km its work covers */}
      {blocks.map((blk) => {
        const x1 = x(frameMinute(new Date(blk.startTime)));
        const x2 = x(frameMinute(new Date(blk.startTime)) + (new Date(blk.endTime).getTime() - new Date(blk.startTime).getTime()) / 60000);
        // Work spans are often a few hundred metres; keep a readable minimum
        // height, centred on the true span so the position stays honest.
        const h = Math.max(8, y(blk.kmTo) - y(blk.kmFrom));
        const top = (y(blk.kmFrom) + y(blk.kmTo)) / 2 - h / 2;
        const label = blk.departments.map((d) => (d === "Engineering" ? "ENG" : d)).join("+");
        return (
          <g key={blk.blockId}
            onMouseMove={(e) => onHover({ kind: "block", block: blk, x: e.clientX, y: e.clientY })}
            onMouseLeave={() => onHover(null)} style={{ cursor: "pointer" }}>
            <rect x={x1} y={top} width={x2 - x1} height={h} rx={2}
              fill={DEPARTMENT_COLORS[blk.departments[0]]} stroke="white" strokeWidth={2} />
            <text x={x2 + 5} y={top + h / 2 + 3.5} fontSize={10} fill={INK} fontWeight={600}>
              {blk.blockId.split("-").pop()} · {label}
            </text>
          </g>
        );
      })}

      {/* Train paths: observed departure and arrival, straight line between */}
      {paths.map((p) => {
        const dep = frameMinute(new Date(p.departed_at));
        const arr = dep + (new Date(p.arrived_at).getTime() - new Date(p.departed_at).getTime()) / 60000;
        const [kmFrom, kmTo] = p.direction === "a_to_b" ? [section.km_start, section.km_end] : [section.km_end, section.km_start];
        return (
          <g key={`${p.train_no}-${p.departed_at}`}
            onMouseMove={(e) => onHover({ kind: "train", path: p, x: e.clientX, y: e.clientY })}
            onMouseLeave={() => onHover(null)} style={{ cursor: "pointer" }}>
            <line x1={x(dep)} y1={y(kmFrom)} x2={x(arr)} y2={y(kmTo)} stroke={INK} strokeWidth={2} strokeLinecap="round" />
            {/* Wider invisible stroke: a 2px line is too thin to hover reliably. */}
            <line x1={x(dep)} y1={y(kmFrom)} x2={x(arr)} y2={y(kmTo)} stroke="transparent" strokeWidth={12} />
          </g>
        );
      })}
    </svg>
  );
}

export default function TimeDistance() {
  const { plan, loading, error } = usePlan();
  const [sectionName, setSectionName] = useState<string | null>(null);
  const [night, setNight] = useState<number | null>(null);
  const [trains, setTrains] = useState<CorridorTrainPaths | null>(null);
  const [trainError, setTrainError] = useState<string | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  const section = plan?.sections.find((s) => s.section === (sectionName ?? "NDLS-GZB")) ?? plan?.sections[0];
  const positioned = useMemo(() => (section ? positionBlocks(section) : []), [section]);
  const nights = useMemo(
    () => Array.from(new Set(positioned.map((b) => nightKey(new Date(b.startTime))))).sort((p, q) => p - q),
    [positioned]
  );
  const activeNight = night !== null && nights.includes(night) ? night : nights[0];

  useEffect(() => {
    if (!section?.ntes_integrated) {
      setTrains(null);
      setTrainError(null);
      return;
    }
    let cancelled = false;
    setTrains(null);
    setTrainError(null);
    fetchTrainPaths(section.section)
      .then((t) => !cancelled && setTrains(t))
      .catch((e: Error) => !cancelled && setTrainError(e.message));
    return () => {
      cancelled = true;
    };
  }, [section?.section, section?.ntes_integrated]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan || !section) return null;

  const nightBlocks = positioned.filter((b) => nightKey(new Date(b.startTime)) === activeNight);
  const allPaths = trains?.paths ?? [];
  const inFrame = allPaths.filter((p) => {
    const dep = frameMinute(new Date(p.departed_at));
    const dur = (new Date(p.arrived_at).getTime() - new Date(p.departed_at).getTime()) / 60000;
    return dep + dur <= FRAME_MIN;
  });

  let noTrainsReason: string | null = null;
  if (!section.ntes_integrated) noTrainsReason = "This section has no NTES data source, so there are no trains to draw.";
  else if (trainError) noTrainsReason = `No train data: ${trainError}. The ntes-adapter service may not be running — blocks are still shown.`;
  else if (trains && trains.boards_fetched_at === null)
    noTrainsReason = `No trains: ntes-adapter has no board for one end of ${section.section}, and a path needs both ends. (RNY was never captured.)`;
  else if (trains && allPaths.length === 0)
    noTrainsReason = `No trains: the ${trains.station_a} and ${trains.station_b} boards share no trains within their ${trains.window_hours}-hour window. On a long section a train rarely shows at both ends inside one capture, so nothing can be paired — see the adapter README.`;

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Time–distance chart</h1>
      <p style={{ fontSize: 13, color: "#475569", marginTop: 4 }}>
        One section, one night. Rectangles are planned blocks (when they run × the km their work covers); lines
        are real trains passing through the section. A line crossing a block means that, on the captured night,
        a train was in the section at that time of day — the occupancy ntes-adapter counts when it estimates
        availability.
      </p>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Section</span>
        {plan.sections.map((s) => (
          <button key={s.section} onClick={() => setSectionName(s.section)}
            style={{
              fontSize: 12, padding: "4px 11px", borderRadius: 5, cursor: "pointer",
              border: s.section === section.section ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: s.section === section.section ? "#0f172a" : "white",
              color: s.section === section.section ? "white" : "#475569",
            }}>
            {s.section}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Night of</span>
        {nights.map((n) => (
          <button key={n} onClick={() => setNight(n)}
            style={{
              fontSize: 12, padding: "3px 10px", borderRadius: 5, cursor: "pointer",
              border: n === activeNight ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: n === activeNight ? "#0f172a" : "white",
              color: n === activeNight ? "white" : "#475569",
            }}>
            {new Date(n).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}
          </button>
        ))}
        {nights.length === 0 && <span style={{ fontSize: 12, color: "#94a3b8" }}>no blocks scheduled on this section</span>}
      </div>

      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#475569", margin: "14px 0 8px", flexWrap: "wrap", alignItems: "center" }}>
        {Object.entries(DEPARTMENT_COLORS).map(([d, c]) => (
          <span key={d} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 12, height: 12, background: c, borderRadius: 2 }} />
            {d} block
          </span>
        ))}
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 18, height: 2, background: INK }} />
          train (paired movement)
        </span>
      </div>

      <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: "6px 4px" }}>
        <Chart section={section} blocks={nightBlocks} paths={inFrame} onHover={setHover} />
      </div>

      <div style={{ fontSize: 12, color: "#64748b", margin: "8px 0 14px", lineHeight: 1.6 }}>
        {nightBlocks.length} block{nightBlocks.length === 1 ? "" : "s"} this night
        {trains && allPaths.length > 0 && (
          <>
            {" "}· {inFrame.length} of {allPaths.length} paired train movements fall in the 20:00–10:00 frame
          </>
        )}
        <br />
        Only a train's departure and arrival are observed; the straight line between them assumes constant speed.
        {" "}{section.section.split("-")[0]} and {section.section.split("-")[1]} sit at the ends of the section's km
        range, which is illustrative, not surveyed chainage.
      </div>

      {trains && allPaths.length > 0 && <ProvenanceBanner provider={trains.provider} stale={trains.stale} />}
      {trains?.provider === "captured_fixture" && allPaths.length > 0 && (
        <p style={{ fontSize: 12, color: "#64748b", marginTop: -8 }}>
          The capture is one night of boards, so the same trains are drawn on whichever night you pick — as clock
          times, not as a forecast for that date.
        </p>
      )}
      {noTrainsReason && (
        <p style={{ fontSize: 12.5, color: "#475569", border: "1px dashed #cbd5e1", borderRadius: 6, padding: "8px 12px" }}>
          {noTrainsReason}
        </p>
      )}

      <details style={{ marginTop: 14 }}>
        <summary style={{ fontSize: 13, cursor: "pointer" }}>Show as tables</summary>
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 8 }}>
          <table style={{ borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "#94a3b8", fontSize: 11 }}>
                <th style={{ padding: "3px 8px" }}>Block</th><th style={{ padding: "3px 8px" }}>Time</th>
                <th style={{ padding: "3px 8px" }}>Km</th><th style={{ padding: "3px 8px" }}>Departments</th>
              </tr>
            </thead>
            <tbody>
              {nightBlocks.map((b) => (
                <tr key={b.blockId} style={{ borderTop: "1px solid #f1f5f9" }}>
                  <td style={{ padding: "3px 8px" }}>{b.blockId}</td>
                  <td style={{ padding: "3px 8px" }}>{hhmm(new Date(b.startTime))}–{hhmm(new Date(b.endTime))}</td>
                  <td style={{ padding: "3px 8px" }}>{b.kmFrom.toFixed(2)}–{b.kmTo.toFixed(2)}</td>
                  <td style={{ padding: "3px 8px" }}>{b.departments.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {allPaths.length > 0 && (
            <table style={{ borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "#94a3b8", fontSize: 11 }}>
                  <th style={{ padding: "3px 8px" }}>Train</th><th style={{ padding: "3px 8px" }}>Direction</th>
                  <th style={{ padding: "3px 8px" }}>Departed</th><th style={{ padding: "3px 8px" }}>Arrived</th>
                </tr>
              </thead>
              <tbody>
                {allPaths.map((p) => (
                  <tr key={`${p.train_no}-${p.departed_at}`} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "3px 8px" }}>{p.train_no} {p.train_name}</td>
                    <td style={{ padding: "3px 8px" }}>
                      {p.direction === "a_to_b" ? `${trains?.station_a} → ${trains?.station_b}` : `${trains?.station_b} → ${trains?.station_a}`}
                    </td>
                    <td style={{ padding: "3px 8px" }}>{hhmm(new Date(p.departed_at))}</td>
                    <td style={{ padding: "3px 8px" }}>{hhmm(new Date(p.arrived_at))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </details>

      {hover && <Tooltip hover={hover} section={section} />}
    </div>
  );
}
