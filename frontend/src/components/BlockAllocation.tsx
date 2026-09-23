import { positionBlocks } from "./CorridorMap";
import { DEPARTMENT_COLORS, REAL_DATA_COLOR } from "../constants/colors";
import type { Department, SectionPlanResult } from "../types";

interface Row {
  blockId: string;
  section: string;
  kmFrom: number;
  kmTo: number;
  start: Date;
  end: Date;
  departments: Department[];
  taskCount: number;
  isRealData: boolean;
}

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function DeptChip({ department }: { department: Department }) {
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        color: "white",
        background: DEPARTMENT_COLORS[department],
        borderRadius: 3,
        padding: "1px 6px",
        marginRight: 4,
        whiteSpace: "nowrap",
      }}
    >
      {department}
    </span>
  );
}

export default function BlockAllocation({ sections }: { sections: SectionPlanResult[] }) {
  const rows: Row[] = sections.flatMap((section) =>
    positionBlocks(section).map((b) => ({
      blockId: b.blockId,
      section: section.section,
      kmFrom: b.kmFrom,
      kmTo: b.kmTo,
      start: new Date(b.startTime),
      end: new Date(b.endTime),
      departments: b.departments,
      taskCount: b.taskCount,
      isRealData: b.isRealData,
    }))
  );

  if (rows.length === 0) return <p style={{ fontSize: 13, color: "#64748b" }}>No blocks scheduled.</p>;

  rows.sort((a, b) => a.start.getTime() - b.start.getTime());

  const days = new Map<string, Row[]>();
  for (const row of rows) {
    const key = dayKey(row.start);
    if (!days.has(key)) days.set(key, []);
    days.get(key)!.push(row);
  }

  const hhmm = (d: Date) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div>
      {Array.from(days.entries()).map(([key, dayRows]) => {
        const totalMin = dayRows.reduce(
          (sum, r) => sum + (r.end.getTime() - r.start.getTime()) / 60000,
          0
        );
        return (
          <div key={key} style={{ marginBottom: 18 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                borderBottom: "2px solid #e2e8f0",
                paddingBottom: 4,
                marginBottom: 2,
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700 }}>
                {dayRows[0].start.toLocaleDateString(undefined, {
                  weekday: "long",
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </div>
              <div style={{ fontSize: 11, color: "#94a3b8" }}>
                {dayRows.length} block{dayRows.length === 1 ? "" : "s"} · {(totalMin / 60).toFixed(1)} h
              </div>
            </div>

            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead>
                <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
                  <th style={{ padding: "5px 6px", fontWeight: 600 }}>Time</th>
                  <th style={{ padding: "5px 6px", fontWeight: 600 }}>Km block</th>
                  <th style={{ padding: "5px 6px", fontWeight: 600 }}>Section</th>
                  <th style={{ padding: "5px 6px", fontWeight: 600 }}>Department</th>
                  <th style={{ padding: "5px 6px", fontWeight: 600 }}>Block</th>
                </tr>
              </thead>
              <tbody>
                {dayRows.map((r) => (
                  <tr key={r.blockId} style={{ borderTop: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "6px", whiteSpace: "nowrap", fontWeight: 600 }}>
                      {hhmm(r.start)}–{hhmm(r.end)}
                      <div style={{ fontSize: 10, color: "#94a3b8", fontWeight: 400 }}>
                        {Math.round((r.end.getTime() - r.start.getTime()) / 60000)} min
                      </div>
                    </td>
                    <td style={{ padding: "6px", whiteSpace: "nowrap" }}>
                      km {r.kmFrom.toFixed(2)}–{r.kmTo.toFixed(2)}
                      <div style={{ fontSize: 10, color: "#94a3b8" }}>
                        {((r.kmTo - r.kmFrom) * 1000).toFixed(0)} m
                      </div>
                    </td>
                    <td style={{ padding: "6px", whiteSpace: "nowrap" }}>
                      {r.section}
                      {r.isRealData && (
                        <span
                          title="Corridor availability for this block came from real NTES data"
                          style={{
                            display: "inline-block",
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: REAL_DATA_COLOR,
                            marginLeft: 6,
                            verticalAlign: "middle",
                          }}
                        />
                      )}
                    </td>
                    <td style={{ padding: "6px" }}>
                      {r.departments.map((d) => (
                        <DeptChip key={d} department={d} />
                      ))}
                      {r.taskCount > 1 && (
                        <span style={{ fontSize: 10, color: "#64748b" }}>{r.taskCount} tasks merged</span>
                      )}
                    </td>
                    <td style={{ padding: "6px", color: "#94a3b8", fontSize: 11, whiteSpace: "nowrap" }}>
                      {r.blockId}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
