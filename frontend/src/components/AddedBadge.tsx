// Marks a block the control office added for work that didn't fit
// (data_source === "added"). No corridor data offered it, so it has no
// train-impact figure. Outlined and colourless, like ReportedBadge, so it
// can't be mistaken for the real-data marker.
export default function AddedBadge() {
  return (
    <span
      title="Added by the control office for work that didn't fit — not a generated or NTES-derived block opportunity."
      style={{
        fontSize: 10,
        fontWeight: 700,
        color: "#0f172a",
        border: "1px dashed #0f172a",
        borderRadius: 4,
        padding: "0 5px",
        letterSpacing: 0.3,
        verticalAlign: "middle",
        whiteSpace: "nowrap",
      }}
    >
      ADDED
    </span>
  );
}
