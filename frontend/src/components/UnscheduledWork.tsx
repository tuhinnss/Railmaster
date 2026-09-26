import { useState } from "react";
import DecisionMessageBox from "./DecisionMessageBox";
import DepartmentBadge from "./DepartmentBadge";
import ReportedBadge from "./ReportedBadge";
import RescheduleForm from "./RescheduleForm";
import SeverityBadge from "./SeverityBadge";
import { BLOCK_TYPE_LABELS } from "../constants/colors";
import type { DecisionMessage } from "../hooks/useBlockDecisions";
import type { AddedBlock, BlockDecision, SectionPlanResult, TaskSummary } from "../types";
import { decidedEnd, decidedStart, span } from "../utils/blockDecisions";

const buttonStyle = { fontSize: 12, padding: "4px 10px", cursor: "pointer" } as const;
const ADD_COLOR = "#4338ca";

// Why an added block isn't in the plan, in one line.
function unusedReason(block: AddedBlock, section: SectionPlanResult, decision: BlockDecision | undefined): string {
  if (decision?.decision === "cancelled") return "It was cancelled; undo that on Block Decisions, or remove it here.";
  const task = section.tasks.find((t) => t.task_id === block.for_task);
  if (!task) return `${block.for_task} is no longer in the backlog.`;
  if (task.scheduled) return `${block.for_task} is scheduled in ${task.block_id} instead.`;
  return `${block.for_task} still doesn't fit — ${task.reason.replace(/^Not scheduled: /, "")}`;
}

function TaskLine({ task }: { task: TaskSummary }) {
  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <DepartmentBadge department={task.department} />
        <span style={{ fontWeight: 600 }}>{task.task_id}</span>
        {task.data_source === "reported" && <ReportedBadge />}
        <SeverityBadge severity={task.severity_code} />
        <span style={{ color: "#475569" }}>
          {task.defect_type.replaceAll("_", " ")} · km {task.km_range[0]}–{task.km_range[1]} · {task.est_duration_min} min ·{" "}
          {BLOCK_TYPE_LABELS[task.block_type_required].toLowerCase()} block
        </span>
      </div>
      <div style={{ fontSize: 12, color: "#64748b", marginTop: 3 }}>{task.reason}</div>
    </>
  );
}

// Below the block map: the work this week's plan couldn't fit, and a way for
// the control office to add a block for it. An added block is held for that
// work -- other work may share it only alongside -- and the week is re-planned
// with it, so nothing else moves unless it has to.
export default function UnscheduledWork({
  section,
  planDays,
  added,
  decisionOf,
  busy,
  message,
  onAdd,
  onRemove,
}: {
  section: SectionPlanResult;
  planDays: string[];
  added: AddedBlock[];
  decisionOf: Map<string, BlockDecision>;
  busy: boolean;
  message: DecisionMessage | null;
  onAdd: (task: TaskSummary, start: string, durationMin: number) => Promise<boolean>;
  onRemove: (blockId: string) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const waiting = section.tasks.filter((t) => !t.scheduled).sort((a, b) => b.priority_score - a.priority_score);
  const scheduled = new Set(section.tasks.filter((t) => t.scheduled).map((t) => t.task_id));
  const inSection = new Set(section.tasks.map((t) => t.task_id));
  const planned = new Map(section.blocks.map((b) => [b.block_id, b]));
  const ours = added.filter((a) => a.section === section.section);

  return (
    <div style={{ marginTop: 28 }}>
      <h2 style={{ fontSize: 15 }}>Work that didn't fit ({waiting.length})</h2>
      <p style={{ fontSize: 12, color: "#64748b", margin: "2px 0 12px", maxWidth: 820 }}>
        No block this week could take this work; the reason is the planner's. <strong>Schedule…</strong> adds a
        block for it at a time you choose. The block is held for that work (other work may share it alongside)
        and the week is re-planned with it. An added block is marked <strong>ADDED</strong>: no corridor data
        offered it, so it carries no train-impact figure.
      </p>

      {message && <DecisionMessageBox message={message} />}

      {waiting.length === 0 ? (
        <p style={{ fontSize: 13, color: "#94a3b8" }}>Everything on {section.section} is scheduled this week.</p>
      ) : (
        waiting.map((task) => {
          const blockedBy = task.depends_on.filter((d) => inSection.has(d) && !scheduled.has(d));
          return (
            <div key={task.task_id} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 14px", marginBottom: 8, fontSize: 12.5 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "flex-start" }}>
                <div>
                  <TaskLine task={task} />
                </div>
                {blockedBy.length > 0 ? (
                  <span style={{ fontSize: 12, color: "#64748b", whiteSpace: "nowrap" }}>Schedule {blockedBy.join(", ")} first</span>
                ) : (
                  <button
                    disabled={busy}
                    onClick={() => setOpen((o) => (o === task.task_id ? null : task.task_id))}
                    style={{ ...buttonStyle, color: ADD_COLOR, whiteSpace: "nowrap" }}
                  >
                    Schedule…
                  </button>
                )}
              </div>
              {open === task.task_id && planDays.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <RescheduleForm
                    section={section.section}
                    kmRange={task.km_range}
                    start={`${planDays[0]}T01:00`}
                    minutes={task.est_duration_min}
                    minMinutes={task.est_duration_min}
                    planDays={planDays}
                    busy={busy}
                    actionLabel="Add block"
                    note={`Adds a ${BLOCK_TYPE_LABELS[task.block_type_required].toLowerCase()} block held for ${task.task_id}; the week is re-planned with it.`}
                    onMove={(start, minutes) => onAdd(task, start, minutes).then((ok) => ok && setOpen(null))}
                  />
                </div>
              )}
            </div>
          );
        })
      )}

      {ours.length > 0 && (
        <>
          <h3 style={{ fontSize: 13, margin: "18px 0 8px" }}>Blocks added by the control office ({ours.length})</h3>
          {ours.map((a) => {
            const block = planned.get(a.block_id);
            const decision = decisionOf.get(a.block_id);
            // Where it is now: in the plan, or moved by a decision, or where it was added.
            const start = block?.start_time ?? (decision ? decidedStart(decision) : a.start_time);
            const end = block?.end_time ?? (decision ? decidedEnd(decision) : a.end_time);
            return (
              <div
                key={a.block_id}
                style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline", padding: "6px 0", borderTop: "1px solid #f1f5f9", fontSize: 12.5 }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{a.block_id}</span>
                  <span style={{ color: "#475569" }}>
                    {" "}
                    · {span(start, end)} · for {a.for_task}
                  </span>
                  <div style={{ fontSize: 12, color: block ? "#15803d" : "#b45309", marginTop: 2 }}>
                    {block
                      ? `In the plan: ${block.task_ids.join(", ")} · ${block.used_min} of ${block.duration_min} min used.`
                      : `Not used by the plan. ${unusedReason(a, section, decision)}`}
                  </div>
                </div>
                <button disabled={busy} onClick={() => onRemove(a.block_id)} style={{ ...buttonStyle, color: "#b91c1c", whiteSpace: "nowrap" }}>
                  Remove
                </button>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
