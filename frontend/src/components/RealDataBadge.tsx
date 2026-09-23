import { REAL_DATA_COLOR } from "../constants/colors";

// Marks a block whose expected_train_impact came from ntes-adapter's real,
// self-collected train-movement history instead of the synthetic generator.
// See backend/app/ntes_bridge.py -- only GHY-LMG and LMG-RNY blocks inside a
// window ntes-adapter has data for ever carry this.
export default function RealDataBadge({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <span
        title="Real NTES-derived data, not synthetic"
        style={{
          display: "inline-block",
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: REAL_DATA_COLOR,
          boxShadow: "0 0 0 1px white",
        }}
      />
    );
  }

  return (
    <span
      title="This block's train-impact figure comes from ntes-adapter's real, self-collected running history, not the synthetic generator."
      style={{
        fontSize: 11,
        fontWeight: 700,
        color: "white",
        background: REAL_DATA_COLOR,
        borderRadius: 4,
        padding: "2px 6px",
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: "white" }} />
      REAL NTES DATA
    </span>
  );
}
