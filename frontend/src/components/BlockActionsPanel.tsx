import { useState } from "react";
import DepartmentBadge from "./DepartmentBadge";
import DecisionMessageBox from "./DecisionMessageBox";
import ReportedBadge from "./ReportedBadge";
import RescheduleForm from "./RescheduleForm";
import { BLOCK_TYPE_LABELS } from "../constants/colors";
import type { DecisionMessage } from "../hooks/useBlockDecisions";
import type { BlockDecision, SectionPlanResult, TaskSummary } from "../types";
import { DECISION_STATUS, decidedEnd, decidedStart, span, workKmRange } from "../utils/blockDecisions";

// Opens when a block is clicked on the Overview's block map: what the block
// is, and the control office's two direct actions on it -- move it, or
// delete it (recorded as a cancellation, so it can be undone here or on
// Block Decisions).
export default function BlockActionsPanel({
  section,
  blockId,
  addedFor,
  decision,
  planDays,
  busy,
  message,
  onMove,
  onDelete,
  onUndo,
  onClose,
}: {
  section: SectionPlanResult;
  blockId: string;
  addedFor: string | undefined; // set when the control office added this block
  decision: BlockDecision | undefined;
  planDays: string[];
  busy: boolean;
  message: DecisionMessage | null;
  onMove: (newStart: string, durationMin: number) => void;
  onDelete: () => void;
  onUndo: () => void;
  onClose: () => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  // A deleted block, or one moved to where no work fits, has left the plan;
  // the saved decision still says where it is.
  const block = section.blocks.find((b) => b.block_id === blockId);
  const start = block?.start_time ?? (decision ? decidedStart(decision) : undefined);
  const end = block?.end_time ?? (decision ? decidedEnd(decision) : undefined);
  const minutes = block?.duration_min ?? (start && end ? Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60_000) : 0);
  const tasks = (block?.task_ids ?? [])
    .map((id) => section.tasks.find((t) => t.task_id === id))
    .filter((t): t is TaskSummary => t !== undefined);
  const status = DECISION_STATUS[decision?.decision ?? "pending"];

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: 400,
        background: "white",
        borderLeft: "1px solid #e2e8f0",
        boxShadow: "-4px 0 16px rgba(0,0,0,0.08)",
        padding: 20,
        overflowY: "auto",
        zIndex: 50,
        fontSize: 13,
      }}
    >
      <button onClick={onClose} style={{ float: "right", border: "none", background: "none", cursor: "pointer", fontSize: 16 }}>
        ✕
      </button>
      <div style={{ fontSize: 12, color: "#64748b" }}>{section.section}</div>
      <h2 style={{ fontSize: 16, margin: "4px 0 6px" }}>{blockId}</h2>
      <span style={{ fontSize: 11, fontWeight: 700, color: status.color, background: status.bg, borderRadius: 4, padding: "2px 8px" }}>
        {status.text.toUpperCase()}
      </span>

      {start && end && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>{span(start, end)}</div>
          <div style={{ color: "#64748b", marginTop: 2 }}>
            {minutes} min{block && ` · ${BLOCK_TYPE_LABELS[block.block_type_possible]} block · ${block.used_min} of ${block.duration_min} min used`}
          </div>
        </div>
      )}
      {addedFor && (
        <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
          <strong>ADDED</strong> by the control office for {addedFor}; remove it under Work that didn't fit.
        </div>
      )}
      {decision?.decision === "rescheduled" && (
        <div style={{ fontSize: 12, color: status.color, marginTop: 4 }}>Moved here from {span(decision.planned_start, decision.planned_end)}.</div>
      )}
      {decision?.decision === "granted_late" && (
        <div style={{ fontSize: 12, color: status.color, marginTop: 4 }}>Granted {decision.minutes_lost} min late.</div>
      )}

      {block ? (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}>
            Work in this block ({tasks.length})
          </div>
          {tasks.map((t) => (
            <div key={t.task_id} style={{ padding: "5px 0", borderTop: "1px solid #f1f5f9" }}>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <DepartmentBadge department={t.department} />
                <span style={{ fontWeight: 600 }}>{t.task_id}</span>
                {t.data_source === "reported" && <ReportedBadge />}
              </div>
              <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
                {t.defect_type.replaceAll("_", " ")} · km {t.km_range[0]}–{t.km_range[1]} · {t.est_duration_min} min
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: "#64748b", marginTop: 14 }}>
          {decision?.decision === "cancelled"
            ? "Deleted from the plan — its work was re-planned into other blocks where it fits."
            : "The plan puts no work in this block any more."}
        </p>
      )}

      <div style={{ marginTop: 18 }}>
        {message && <DecisionMessageBox message={message} />}

        {start && (
          <>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", margin: "4px 0 6px" }}>
              Reschedule
            </div>
            {/* keyed on the time so the form resets to wherever the block now is */}
            <RescheduleForm
              key={`${start}-${minutes}`}
              section={section.section}
              kmRange={workKmRange(section, block?.task_ids ?? [])}
              start={start}
              minutes={minutes}
              planDays={planDays}
              busy={busy}
              onMove={onMove}
            />
          </>
        )}

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 14 }}>
          {block &&
            (confirmDelete ? (
              <>
                <span style={{ fontSize: 12, color: "#b91c1c" }}>Delete this block? Its work is re-planned elsewhere if it fits.</span>
                <button
                  disabled={busy}
                  onClick={() => {
                    setConfirmDelete(false);
                    onDelete();
                  }}
                  style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer", color: "white", background: "#b91c1c", border: "1px solid #b91c1c", borderRadius: 4 }}
                >
                  Delete
                </button>
                <button onClick={() => setConfirmDelete(false)} style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer" }}>
                  Keep it
                </button>
              </>
            ) : (
              <button disabled={busy} onClick={() => setConfirmDelete(true)} style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer", color: "#b91c1c" }}>
                Delete block
              </button>
            ))}
          {decision && (
            <button disabled={busy} onClick={onUndo} style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer" }}>
              Undo {decision.decision === "cancelled" ? "delete" : decision.decision === "rescheduled" ? "move" : "decision"}
            </button>
          )}
          {busy && <span style={{ fontSize: 12, color: "#64748b" }}>Re-planning…</span>}
        </div>
        <p style={{ fontSize: 11, color: "#94a3b8", marginTop: 14 }}>
          Every change is saved and can be undone here or on Block Decisions. The timetable check covers
          booked passenger trains only — not goods trains, live delays or other blocks. Check Corridor
          Traffic for live running.
        </p>
      </div>
    </div>
  );
}
