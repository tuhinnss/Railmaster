// Marks a task that came from the Report Defect page rather than the
// generated backlog (TaskSummary.data_source === "reported"). Outlined and
// colourless on purpose: department, severity and real-data markers already
// use colour, and this must not read as any of them.
export default function ReportedBadge() {
  return (
    <span
      title="Reported on the Report Defect page — entered by a user, not from the generated backlog."
      style={{
        fontSize: 10,
        fontWeight: 700,
        color: "#0f172a",
        border: "1px solid #0f172a",
        borderRadius: 4,
        padding: "0 5px",
        marginLeft: 6,
        letterSpacing: 0.3,
        verticalAlign: "middle",
      }}
    >
      REPORTED
    </span>
  );
}
