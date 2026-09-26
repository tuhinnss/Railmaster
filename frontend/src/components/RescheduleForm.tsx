import { useState } from "react";
import { dateLabel, dayKey } from "../utils/blockDecisions";
import { hhmm } from "../utils/time";

const inputStyle = { fontSize: 12, padding: "3px 5px", border: "1px solid #cbd5e1", borderRadius: 4 } as const;
const MOVE_COLOR = "#4338ca";

// New day, start time and length for a block. The days on offer are the plan
// week only; the backend refuses anything outside it.
export default function RescheduleForm({
  start,
  minutes,
  planDays,
  busy,
  onMove,
}: {
  start: string;
  minutes: number;
  planDays: string[];
  busy: boolean;
  onMove: (newStart: string, durationMin: number) => void;
}) {
  const [day, setDay] = useState(dayKey(start));
  const [time, setTime] = useState(hhmm(start));
  const [length, setLength] = useState(minutes);

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        alignItems: "flex-end",
        flexWrap: "wrap",
        padding: "10px 12px",
        background: "#f8fafc",
        border: "1px solid #e2e8f0",
        borderRadius: 6,
        fontSize: 11,
        color: "#64748b",
      }}
    >
      <label style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        Day
        <select value={day} onChange={(e) => setDay(e.target.value)} style={inputStyle}>
          {planDays.map((d) => (
            <option key={d} value={d}>
              {dateLabel(d)}
            </option>
          ))}
        </select>
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        Starts at
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} style={inputStyle} />
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        Length (min)
        <input type="number" min={15} step={15} value={length} onChange={(e) => setLength(Number(e.target.value))} style={{ ...inputStyle, width: 70 }} />
      </label>
      <button
        disabled={busy || !time || length <= 0}
        // Local wall-clock time with no zone, like every block in the plan.
        onClick={() => onMove(`${day}T${time}`, length)}
        style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer", color: MOVE_COLOR, fontWeight: 600 }}
      >
        Move block
      </button>
      <span style={{ flexBasis: "100%", fontSize: 11 }}>
        The week is re-planned around the new time; work that no longer fits moves or drops out.
      </span>
    </div>
  );
}
