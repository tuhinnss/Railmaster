import type { BlockDecision, BlockDecisionKind, SectionPlanResult } from "../types";
import { DECISION_STATUS, decidedEnd, decidedStart, span } from "../utils/blockDecisions";

const WHY: Partial<Record<BlockDecisionKind, string>> = {
  cancelled: "Deleted; its work was re-planned into other blocks where it fits.",
  granted_late: "What is left of it is too short for any of the work.",
  rescheduled: "No work fits better at its new time than where it already is.",
};

// Blocks a decision took out of the plan: every deleted one, and a late grant
// or a move that left no work fitting. They are gone from the map, so they
// are listed under it, each with Undo -- otherwise a deleted block could only
// be restored while its panel was still open.
export default function OffPlanBlocks({
  section,
  decisions,
  busy,
  onOpen,
  onUndo,
}: {
  section: SectionPlanResult;
  decisions: BlockDecision[];
  busy: boolean;
  onOpen: (blockId: string) => void;
  onUndo: (blockId: string) => void;
}) {
  const inPlan = new Set(section.blocks.map((b) => b.block_id));
  const off = decisions
    .filter((d) => d.section === section.section && !inPlan.has(d.block_id))
    .sort((a, b) => decidedStart(a).localeCompare(decidedStart(b)));
  if (off.length === 0) return null;

  return (
    <div style={{ marginTop: 20 }}>
      <h2 style={{ fontSize: 15, marginBottom: 6 }}>Blocks off the plan ({off.length})</h2>
      {off.map((d) => {
        const status = DECISION_STATUS[d.decision];
        return (
          <div
            key={d.block_id}
            style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", padding: "6px 0", borderTop: "1px solid #f1f5f9", fontSize: 12.5 }}
          >
            <div>
              <button
                onClick={() => onOpen(d.block_id)}
                style={{ border: "none", background: "none", padding: 0, font: "inherit", fontWeight: 600, cursor: "pointer", textDecoration: "underline" }}
              >
                {d.block_id}
              </button>
              <span style={{ color: "#475569" }}> · {span(decidedStart(d), decidedEnd(d))} </span>
              <span style={{ fontSize: 11, fontWeight: 700, color: status.color, background: status.bg, borderRadius: 4, padding: "1px 6px" }}>
                {status.text.toUpperCase()}
              </span>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>{WHY[d.decision] ?? "The plan no longer puts any work in it."}</div>
            </div>
            <button disabled={busy} onClick={() => onUndo(d.block_id)} style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer", whiteSpace: "nowrap" }}>
              Undo
            </button>
          </div>
        );
      })}
    </div>
  );
}
