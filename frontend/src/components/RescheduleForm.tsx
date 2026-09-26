import { useEffect, useState } from "react";
import { fetchQuietSlots, fetchTimetableCheck } from "../api/client";
import type { QuietSlots, TimetableCheck, TrainPass } from "../types";
import { dateLabel, dayKey } from "../utils/blockDecisions";
import { hhmm } from "../utils/time";

const inputStyle = { fontSize: 12, padding: "3px 5px", border: "1px solid #cbd5e1", borderRadius: 4 } as const;
const MOVE_COLOR = "#4338ca";
const SHOWN_TRAINS = 4;

function fetchedLabel(source: { provider: string | null; fetched_at: string | null }): string {
  const when = source.fetched_at
    ? new Date(source.fetched_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    : "unknown time";
  if (source.provider === "ntes_live") return `NTES timetable, fetched ${when}`;
  if (source.provider === "captured_fixture") return `NTES timetable captured ${when} (replayed copy)`;
  return `timetable from ${source.provider ?? "an unknown source"}, ${when}`;
}

function trainLine(t: TrainPass): string {
  return `${t.train_no} ${t.train_name} (${t.direction}) ~${hhmm(t.passes_from)}`;
}

// What the booked timetable says about the chosen time. A warning, never a
// veto: trains are held or regulated around a block in practice. With no
// timetable it says "not checked" -- never "no trains".
function TimetableLine({ check, kmFrom, kmTo }: { check: TimetableCheck; kmFrom: number; kmTo: number }) {
  if (!check.available) {
    return <div style={{ color: "#64748b", fontStyle: "italic" }}>{check.reason}</div>;
  }
  const n = check.trains.length;
  return (
    <div>
      {n === 0 ? (
        <div style={{ color: "#15803d", fontWeight: 600 }}>
          No passenger trains booked over km {kmFrom}–{kmTo} then.
        </div>
      ) : (
        <div style={{ color: "#b45309" }}>
          <div style={{ fontWeight: 600 }}>
            ⚠ {n} passenger train{n === 1 ? "" : "s"} booked over km {kmFrom}–{kmTo} then — they would have to be held
            or regulated:
          </div>
          <ul style={{ margin: "3px 0 0", paddingLeft: 16 }}>
            {check.trains.slice(0, SHOWN_TRAINS).map((t) => (
              <li key={`${t.train_no}-${t.passes_from}`}>{trainLine(t)}</li>
            ))}
            {n > SHOWN_TRAINS && <li>and {n - SHOWN_TRAINS} more</li>}
          </ul>
        </div>
      )}
      <div style={{ color: "#94a3b8", marginTop: 4 }}>
        {fetchedLabel(check)}. Passenger trains only — goods trains are in no public timetable. Passing times are
        estimated at a steady speed along the section; both directions count.
        {check.not_counted > 0 && ` ${check.not_counted} listed trains start or end at a neighbouring station and aren't counted.`}
      </div>
    </div>
  );
}

// New day, start time and length for a block, checked against the booked
// timetable as you choose. The days on offer are the plan week only; the
// backend refuses anything outside it.
export default function RescheduleForm({
  section,
  kmRange,
  start,
  minutes,
  planDays,
  busy,
  onMove,
}: {
  section: string;
  kmRange: [number, number];
  start: string;
  minutes: number;
  planDays: string[];
  busy: boolean;
  onMove: (newStart: string, durationMin: number) => void;
}) {
  const [day, setDay] = useState(dayKey(start));
  const [time, setTime] = useState(hhmm(start));
  const [length, setLength] = useState(minutes);
  const [check, setCheck] = useState<TimetableCheck | null>(null);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [slots, setSlots] = useState<QuietSlots | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [kmFrom, kmTo] = kmRange;
  // Local wall-clock time with no zone, like every block in the plan.
  const chosenStart = `${day}T${time}`;

  // Re-check a moment after the inputs settle, not on every keystroke.
  useEffect(() => {
    if (!time || length <= 0) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchTimetableCheck(section, kmFrom, kmTo, chosenStart, length)
        .then((c) => {
          if (cancelled) return;
          setCheck(c);
          setCheckError(null);
        })
        .catch((e: Error) => {
          if (!cancelled) setCheckError(e.message);
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [section, kmFrom, kmTo, chosenStart, length, time]);

  const suggest = () => {
    setSuggesting(true);
    fetchQuietSlots(section, kmFrom, kmTo, day, length, chosenStart)
      .then(setSlots)
      .catch((e: Error) => setCheckError(e.message))
      .finally(() => setSuggesting(false));
  };

  return (
    <div
      style={{
        padding: "10px 12px",
        background: "#f8fafc",
        border: "1px solid #e2e8f0",
        borderRadius: 6,
        fontSize: 11,
        color: "#64748b",
      }}
    >
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          Day
          <select
            value={day}
            onChange={(e) => {
              setDay(e.target.value);
              setSlots(null);
            }}
            style={inputStyle}
          >
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
          <input
            type="number"
            min={15}
            step={15}
            value={length}
            onChange={(e) => {
              setLength(Number(e.target.value));
              setSlots(null);
            }}
            style={{ ...inputStyle, width: 70 }}
          />
        </label>
        <button
          disabled={busy || !time || length <= 0}
          onClick={() => onMove(chosenStart, length)}
          style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer", color: MOVE_COLOR, fontWeight: 600 }}
        >
          Move block
        </button>
        <button
          disabled={suggesting || length <= 0}
          onClick={suggest}
          style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer" }}
        >
          {suggesting ? "Looking…" : "Suggest quiet times"}
        </button>
      </div>

      <div style={{ marginTop: 10, fontSize: 11.5 }}>
        {checkError ? (
          <div style={{ color: "#64748b", fontStyle: "italic" }}>Couldn't check the timetable: {checkError}</div>
        ) : check ? (
          <TimetableLine check={check} kmFrom={kmFrom} kmTo={kmTo} />
        ) : (
          <div>Checking the timetable…</div>
        )}
      </div>

      {slots && (
        <div style={{ marginTop: 10, fontSize: 11.5 }}>
          {!slots.available ? (
            <div style={{ fontStyle: "italic" }}>{slots.reason}</div>
          ) : (
            <>
              <div style={{ marginBottom: 4 }}>
                Quietest {length}-minute starts on {dateLabel(day)} (fewest booked trains, nearest your chosen time first
                among equals) — click one to use it:
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {slots.slots.map((s) => (
                  <button
                    key={s.start}
                    onClick={() => setTime(hhmm(s.start))}
                    title={s.trains.map(trainLine).join("\n") || "No passenger trains booked"}
                    style={{
                      fontSize: 11.5,
                      padding: "3px 8px",
                      cursor: "pointer",
                      background: "white",
                      border: `1px solid ${s.trains.length === 0 ? "#86efac" : "#fcd34d"}`,
                      borderRadius: 4,
                    }}
                  >
                    {hhmm(s.start)}–{hhmm(s.end)} ·{" "}
                    {s.trains.length === 0 ? "no trains" : `${s.trains.length} train${s.trains.length === 1 ? "" : "s"}`}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      <div style={{ marginTop: 8, fontSize: 11 }}>
        The week is re-planned around the new time; work that no longer fits moves or drops out.
      </div>
    </div>
  );
}
