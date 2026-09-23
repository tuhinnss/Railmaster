import { useEffect, useState } from "react";
import { fetchCorridorTrains } from "../api/client";
import { REAL_DATA_COLOR } from "../constants/colors";
import type { LiveCorridorStatus, StationLiveBoard, TrainEvent } from "../types";

const CORRIDORS = ["GHY-LMG", "LMG-RNY"];

// What each adapter provider actually means, stated plainly. A demo that
// shows canned trains without saying so is worse than showing nothing.
const PROVENANCE: Record<string, { label: string; detail: string; real: boolean }> = {
  captured_fixture: {
    label: "Real NTES capture",
    detail:
      "Genuine NTES Live Station responses captured during investigation — real train numbers, names, delays and platforms. Times are real; the calendar date they are shown against is today's, not the date they were observed.",
    real: true,
  },
  ntes_live: {
    label: "Live NTES",
    detail: "Fetched from NTES now via the unofficial Live Station query.",
    real: true,
  },
  mock: {
    label: "Mock data",
    detail: "Canned, deterministic placeholder trains. Not real — do not present these as observed traffic.",
    real: false,
  },
};

function StatusPill({ event }: { event: TrainEvent }) {
  const map: Record<string, { text: string; bg: string }> = {
    on_time: { text: "on time", bg: "#059669" },
    delayed: { text: event.delay_minutes ? `+${event.delay_minutes}m` : "delayed", bg: "#dc2626" },
    source: { text: "originates", bg: "#64748b" },
    terminating: { text: "terminates", bg: "#64748b" },
    unknown: { text: "unknown", bg: "#94a3b8" },
  };
  const s = map[event.status] ?? map.unknown;
  return (
    <span style={{ fontSize: 11, fontWeight: 600, color: "white", background: s.bg, borderRadius: 4, padding: "1px 6px" }}>
      {s.text}
    </span>
  );
}

function StationBoard({ board, stationLabel }: { board: StationLiveBoard | null; stationLabel: string }) {
  if (board === null) {
    return (
      <div style={{ flex: 1, border: "1px dashed #cbd5e1", borderRadius: 8, padding: 16 }}>
        <h3 style={{ fontSize: 14, margin: "0 0 6px" }}>{stationLabel}</h3>
        <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>
          No data. This station was never captured, so there is nothing real to show — rather than
          substituting placeholder trains.
        </p>
      </div>
    );
  }

  const sorted = [...board.events].sort((a, b) => {
    const ta = a.actual_or_expected_time ? new Date(a.actual_or_expected_time).getTime() : Infinity;
    const tb = b.actual_or_expected_time ? new Date(b.actual_or_expected_time).getTime() : Infinity;
    return ta - tb;
  });

  return (
    <div style={{ flex: 1, border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, minWidth: 0 }}>
      <h3 style={{ fontSize: 14, margin: "0 0 2px" }}>
        {stationLabel} <span style={{ color: "#94a3b8", fontWeight: 400 }}>({board.station_code})</span>
      </h3>
      <div style={{ fontSize: 11, color: "#94a3b8", marginBottom: 10 }}>
        {board.events.length} movements · next {board.window_hours}h window
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <tbody>
          {sorted.map((e, i) => (
            <tr key={`${e.train_no}-${e.event_type}-${i}`} style={{ borderTop: "1px solid #f1f5f9" }}>
              <td style={{ padding: "6px 4px", whiteSpace: "nowrap", color: "#475569" }}>
                {e.actual_or_expected_time
                  ? new Date(e.actual_or_expected_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                  : "—"}
              </td>
              <td style={{ padding: "6px 4px" }}>
                <div style={{ fontWeight: 600 }}>{e.train_no}</div>
                <div style={{ color: "#64748b", fontSize: 11 }}>{e.train_name}</div>
              </td>
              <td style={{ padding: "6px 4px", color: "#64748b" }}>{e.event_type === "arrival" ? "arr" : "dep"}</td>
              <td style={{ padding: "6px 4px" }}>
                <StatusPill event={e} />
              </td>
              <td style={{ padding: "6px 4px", color: "#94a3b8", whiteSpace: "nowrap" }}>
                {e.platform ? `PF ${e.platform}` : ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CorridorTraffic() {
  const [corridor, setCorridor] = useState(CORRIDORS[0]);
  const [data, setData] = useState<LiveCorridorStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCorridorTrains(corridor)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [corridor]);

  const provenance = data ? PROVENANCE[data.provider] : undefined;

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Corridor Traffic</h1>
      <p style={{ fontSize: 13, color: "#475569", marginTop: 4 }}>
        Train movements at both ends of the NTES-integrated corridors — the traffic that maintenance
        blocks on these sections have to fit around.
      </p>

      <div style={{ display: "flex", gap: 8, margin: "14px 0" }}>
        {CORRIDORS.map((c) => (
          <button
            key={c}
            onClick={() => setCorridor(c)}
            style={{
              fontSize: 13,
              padding: "5px 12px",
              borderRadius: 6,
              cursor: "pointer",
              border: c === corridor ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: c === corridor ? "#0f172a" : "white",
              color: c === corridor ? "white" : "#475569",
            }}
          >
            {c}
          </button>
        ))}
      </div>

      {provenance && (
        <div
          style={{
            border: `1px solid ${provenance.real ? REAL_DATA_COLOR : "#f59e0b"}`,
            background: provenance.real ? "#ecfeff" : "#fffbeb",
            borderRadius: 8,
            padding: "10px 14px",
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 700, color: provenance.real ? REAL_DATA_COLOR : "#b45309" }}>
            {provenance.label.toUpperCase()}
            {data?.stale && " · STALE"}
          </div>
          <div style={{ fontSize: 12, color: "#475569", marginTop: 3 }}>{provenance.detail}</div>
        </div>
      )}

      {loading && <p>Loading…</p>}
      {error && (
        <p style={{ color: "#dc2626", fontSize: 13 }}>
          Could not load train data: {error}. The ntes-adapter service may not be running.
        </p>
      )}

      {data && !loading && (
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          <StationBoard board={data.station_a} stationLabel={corridor.split("-")[0]} />
          <StationBoard board={data.station_b} stationLabel={corridor.split("-")[1]} />
        </div>
      )}
    </div>
  );
}
