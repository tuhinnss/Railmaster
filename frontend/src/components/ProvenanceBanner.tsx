import { REAL_DATA_COLOR } from "../constants/colors";

// Corridors ntes-adapter covers. Mirrors NTES_INTEGRATED_SECTIONS in
// backend/app/datagen/reference_data.py.
export const NTES_CORRIDORS = ["GHY-LMG", "LMG-RNY", "NDLS-GZB"];

// What each adapter provider actually means, stated plainly. A demo that
// shows canned trains without saying so is worse than showing nothing.
export const PROVENANCE: Record<string, { label: string; detail: string; real: boolean }> = {
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

export default function ProvenanceBanner({ provider, stale }: { provider: string; stale: boolean }) {
  const provenance = PROVENANCE[provider] ?? {
    label: `Unknown source (${provider})`,
    detail: "The adapter reported a provider this dashboard doesn't recognise — treat as unverified.",
    real: false,
  };

  return (
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
        {stale && " · STALE"}
      </div>
      <div style={{ fontSize: 12, color: "#475569", marginTop: 3 }}>{provenance.detail}</div>
    </div>
  );
}
