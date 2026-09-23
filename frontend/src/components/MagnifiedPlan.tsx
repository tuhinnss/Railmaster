import { useMemo, useState } from "react";
import { DEPARTMENT_COLORS, REAL_DATA_COLOR } from "../constants/colors";
import type { Department, SectionPlanResult, TaskSummary } from "../types";

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;
const ZOOM_LEVELS = [30, 60, 120];
const LABEL_ROW_HEIGHT = 46;
const BAR_HEIGHT = 26;

const DEPT_ABBR: Record<Department, string> = {
  Engineering: "ENG",
  TRD: "TRD",
  "S&T": "S&T",
};

/** Floor to midnight / ceil to the next midnight, so the axis starts and ends
 *  on day boundaries regardless of when the first block happens to begin. */
function dayFloor(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function planTimeRange(sections: SectionPlanResult[]): { start: number; end: number } | null {
  const starts = sections.flatMap((s) => s.blocks.map((b) => new Date(b.start_time).getTime()));
  const ends = sections.flatMap((s) => s.blocks.map((b) => new Date(b.end_time).getTime()));
  if (starts.length === 0) return null;
  return { start: dayFloor(Math.min(...starts)), end: dayFloor(Math.max(...ends)) + DAY_MS };
}

export default function MagnifiedPlan({
  sections,
  onSelectTask,
}: {
  sections: SectionPlanResult[];
  onSelectTask: (task: TaskSummary, section: SectionPlanResult) => void;
}) {
  const [pxPerHour, setPxPerHour] = useState(60);
  const range = useMemo(() => planTimeRange(sections), [sections]);

  if (range === null) return <p style={{ fontSize: 13, color: "#64748b" }}>No scheduled blocks to show.</p>;

  const totalHours = (range.end - range.start) / HOUR_MS;
  const width = totalHours * pxPerHour;
  const dayCount = Math.round((range.end - range.start) / DAY_MS);
  const xOf = (ms: number) => ((ms - range.start) / HOUR_MS) * pxPerHour;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Zoom</span>
        {ZOOM_LEVELS.map((z) => (
          <button
            key={z}
            onClick={() => setPxPerHour(z)}
            style={{
              fontSize: 12,
              padding: "3px 10px",
              borderRadius: 5,
              cursor: "pointer",
              border: z === pxPerHour ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: z === pxPerHour ? "#0f172a" : "white",
              color: z === pxPerHour ? "white" : "#475569",
            }}
          >
            {z === 30 ? "Fit more" : z === 60 ? "Normal" : "Detail"}
          </button>
        ))}
        <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: 4 }}>scroll sideways →</span>
      </div>

      <div style={{ display: "flex", border: "1px solid #e2e8f0", borderRadius: 8, overflow: "hidden" }}>
        {/* Frozen section labels, so you keep your bearings while scrolling */}
        <div style={{ flex: "0 0 104px", borderRight: "1px solid #e2e8f0", background: "#f8fafc" }}>
          <div style={{ height: 30, borderBottom: "1px solid #e2e8f0" }} />
          {sections.map((s) => (
            <div
              key={s.section}
              style={{
                height: BAR_HEIGHT + LABEL_ROW_HEIGHT,
                display: "flex",
                alignItems: "center",
                padding: "0 10px",
                fontSize: 12,
                fontWeight: 600,
                borderBottom: "1px solid #f1f5f9",
              }}
            >
              {s.section}
            </div>
          ))}
        </div>

        <div style={{ overflowX: "auto", flex: 1 }}>
          <div style={{ width, position: "relative" }}>
            {/* Date header */}
            <div style={{ display: "flex", height: 30, borderBottom: "1px solid #e2e8f0" }}>
              {Array.from({ length: dayCount }, (_, i) => {
                const dayStart = range.start + i * DAY_MS;
                return (
                  <div
                    key={dayStart}
                    style={{
                      width: 24 * pxPerHour,
                      borderRight: "1px solid #e2e8f0",
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#475569",
                      display: "flex",
                      alignItems: "center",
                      paddingLeft: 8,
                      boxSizing: "border-box",
                    }}
                  >
                    {new Date(dayStart).toLocaleDateString(undefined, {
                      weekday: "short",
                      day: "numeric",
                      month: "short",
                    })}
                  </div>
                );
              })}
            </div>

            {sections.map((section) => (
              <div
                key={section.section}
                style={{
                  position: "relative",
                  height: BAR_HEIGHT + LABEL_ROW_HEIGHT,
                  borderBottom: "1px solid #f1f5f9",
                }}
              >
                {/* Night shading: blocks live here, so it orients the eye */}
                {Array.from({ length: dayCount }, (_, i) => (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      left: i * 24 * pxPerHour,
                      width: 5 * pxPerHour,
                      top: 0,
                      bottom: 0,
                      background: "#f8fafc",
                    }}
                  />
                ))}
                {Array.from({ length: dayCount }, (_, i) => (
                  <div
                    key={`d${i}`}
                    style={{
                      position: "absolute",
                      left: i * 24 * pxPerHour,
                      top: 0,
                      bottom: 0,
                      borderLeft: "1px solid #e2e8f0",
                    }}
                  />
                ))}

                {section.blocks.map((block) => {
                  const start = new Date(block.start_time);
                  const end = new Date(block.end_time);
                  const left = xOf(start.getTime());
                  const w = Math.max(xOf(end.getTime()) - left, 8);

                  const tasks = block.task_ids
                    .map((id) => section.tasks.find((t) => t.task_id === id))
                    .filter((t): t is TaskSummary => Boolean(t));
                  const departments = Array.from(new Set(tasks.map((t) => t.department)));
                  const isRealData = block.data_source === "ntes_live";

                  const timeLabel = `${start.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}–${end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
                  const dateLabel = start.toLocaleDateString(undefined, {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                  });
                  const deptLabel = departments.map((d) => DEPT_ABBR[d]).join(" + ");

                  return (
                    <div
                      key={block.block_id}
                      onClick={() => tasks[0] && onSelectTask(tasks[0], section)}
                      style={{ position: "absolute", left, width: w, top: 4, cursor: "pointer" }}
                      title={`${block.block_id}\n${dateLabel} ${timeLabel}\n${tasks.length} task(s): ${departments.join(
                        ", "
                      )}\nBlock type: ${block.block_type_possible}${isRealData ? "\nReal NTES data" : ""}`}
                    >
                      <div
                        style={{
                          display: "flex",
                          height: BAR_HEIGHT,
                          borderRadius: 4,
                          overflow: "hidden",
                          boxShadow: isRealData ? `0 0 0 2px ${REAL_DATA_COLOR}` : "none",
                        }}
                      >
                        {departments.map((d) => (
                          <div
                            key={d}
                            style={{
                              flex: 1,
                              background: DEPARTMENT_COLORS[d],
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: "white",
                              fontSize: 10,
                              fontWeight: 700,
                            }}
                          >
                            {w > 54 ? DEPT_ABBR[d] : ""}
                          </div>
                        ))}
                      </div>
                      <div style={{ fontSize: 10, lineHeight: 1.35, color: "#475569", paddingTop: 3, overflow: "hidden" }}>
                        <div style={{ fontWeight: 600, whiteSpace: "nowrap" }}>{timeLabel}</div>
                        <div style={{ whiteSpace: "nowrap", color: "#64748b" }}>{dateLabel}</div>
                        <div style={{ whiteSpace: "nowrap", color: "#94a3b8" }}>
                          {deptLabel}
                          {tasks.length > 1 ? ` · ${tasks.length} tasks` : ""}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
