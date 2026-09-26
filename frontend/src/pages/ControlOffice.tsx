import { useState } from "react";
import { Link } from "react-router-dom";
import DecisionMessageBox from "../components/DecisionMessageBox";
import DepartmentBadge from "../components/DepartmentBadge";
import ReportedBadge from "../components/ReportedBadge";
import RescheduleForm from "../components/RescheduleForm";
import { BLOCK_TYPE_LABELS } from "../constants/colors";
import { usePlan } from "../context/PlanContext";
import { useBlockDecisions, type DecideOptions } from "../hooks/useBlockDecisions";
import type { BlockDecision, BlockDecisionKind, ScheduledBlockSummary, SectionPlanResult, TaskSummary } from "../types";
import {
  DECISION_STATUS,
  dateLabel,
  decidedEnd,
  decidedStart,
  nightKey,
  nightLabel,
  planDaysOf,
  span,
} from "../utils/blockDecisions";
import { hhmm } from "../utils/time";

const buttonStyle = { fontSize: 12, padding: "4px 10px", cursor: "pointer" } as const;
const inputStyle = { fontSize: 12, padding: "3px 5px", border: "1px solid #cbd5e1", borderRadius: 4 } as const;

function BlockCard({
  block,
  decision,
  section,
  planDays,
  busy,
  onDecide,
  onUndo,
}: {
  block: ScheduledBlockSummary | null; // null when the plan no longer uses it (cancelled, or nothing fits)
  decision: BlockDecision | undefined;
  section: SectionPlanResult;
  planDays: string[];
  busy: boolean;
  onDecide: (kind: BlockDecisionKind, opts?: DecideOptions) => void;
  onUndo: () => void;
}) {
  const status = DECISION_STATUS[decision?.decision ?? "pending"];
  const start = block?.start_time ?? decidedStart(decision!);
  const end = block?.end_time ?? decidedEnd(decision!);
  const blockId = block?.block_id ?? decision!.block_id;
  const minutes = block?.duration_min ?? Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60_000);
  const tasks = (block?.task_ids ?? [])
    .map((id) => section.tasks.find((t) => t.task_id === id))
    .filter((t): t is TaskSummary => t !== undefined);

  const [late, setLate] = useState(decision?.minutes_lost || 30);
  const [moving, setMoving] = useState(false);

  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderLeft: `4px solid ${status.color}`,
        borderRadius: 8,
        padding: "12px 14px",
        marginBottom: 10,
        opacity: decision?.decision === "cancelled" ? 0.85 : 1,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <div>
          <span style={{ fontSize: 16, fontWeight: 700 }}>
            {hhmm(start)}–{hhmm(end)}
          </span>
          <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>
            {minutes} min
            {block && ` · ${BLOCK_TYPE_LABELS[block.block_type_possible]} block`}
            {" · "}
            {blockId}
          </span>
          {decision?.decision === "granted_late" && (
            <div style={{ fontSize: 11.5, color: status.color, marginTop: 2 }}>
              Planned {hhmm(decision.planned_start)}–{hhmm(decision.planned_end)}; granted {decision.minutes_lost} min late.
            </div>
          )}
          {decision?.decision === "rescheduled" && (
            <div style={{ fontSize: 11.5, color: status.color, marginTop: 2 }}>
              Moved here from {span(decision.planned_start, decision.planned_end)}.
            </div>
          )}
        </div>
        <span style={{ fontSize: 11, fontWeight: 700, color: status.color, background: status.bg, borderRadius: 4, padding: "2px 8px" }}>
          {status.text.toUpperCase()}
        </span>
      </div>

      {block ? (
        <div style={{ margin: "8px 0 10px", fontSize: 12.5 }}>
          <div style={{ color: "#64748b", fontSize: 11.5, marginBottom: 4 }}>
            {tasks.length} task{tasks.length === 1 ? "" : "s"} · {block.used_min} of {block.duration_min} min used
          </div>
          {tasks.map((t) => (
            <div key={t.task_id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "2px 0" }}>
              <DepartmentBadge department={t.department} />
              <span style={{ fontWeight: 600 }}>{t.task_id}</span>
              {t.data_source === "reported" && <ReportedBadge />}
              <span style={{ color: "#64748b" }}>
                {t.defect_type.replaceAll("_", " ")} · km {t.km_range[0]}–{t.km_range[1]} · {t.est_duration_min} min
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ margin: "8px 0 10px", fontSize: 12.5, color: "#64748b" }}>
          {decision?.decision === "cancelled"
            ? "Cancelled — its work was replanned into other blocks where it fits."
            : decision?.decision === "granted_late"
              ? "The plan no longer uses this block: what is left of it is too short for any of the work."
              : decision?.decision === "rescheduled"
                ? "The plan puts no work in this block at its new time: none of the work fits there better than where it is."
                : "The plan no longer puts any work in this block."}
        </div>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {block && (
          <>
            <button disabled={busy || decision?.decision === "granted"} onClick={() => onDecide("granted")} style={buttonStyle}>
              Grant
            </button>
            <span style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: 12, color: "#475569" }}>
              <button disabled={busy} onClick={() => onDecide("granted_late", { minutesLost: late })} style={buttonStyle}>
                Granted late by
              </button>
              <input type="number" min={5} step={5} value={late} onChange={(e) => setLate(Number(e.target.value))} style={{ ...inputStyle, width: 56 }} />
              min
            </span>
          </>
        )}
        <button disabled={busy} onClick={() => setMoving((m) => !m)} style={{ ...buttonStyle, color: DECISION_STATUS.rescheduled.color }}>
          Reschedule…
        </button>
        {block && (
          <button disabled={busy} onClick={() => onDecide("cancelled")} style={{ ...buttonStyle, color: "#b91c1c" }}>
            Cancel block
          </button>
        )}
        {decision && (
          <button disabled={busy} onClick={onUndo} style={{ fontSize: 12, border: "none", background: "none", color: "#64748b", cursor: "pointer" }}>
            undo decision
          </button>
        )}
      </div>

      {moving && (
        <div style={{ marginTop: 10 }}>
          <RescheduleForm
            start={start}
            minutes={minutes}
            planDays={planDays}
            busy={busy}
            onMove={(newStart, durationMin) => onDecide("rescheduled", { newStart, durationMin })}
          />
        </div>
      )}
    </div>
  );
}

export default function ControlOffice() {
  const { plan, loading, error } = usePlan();
  const ops = useBlockDecisions();
  const [selected, setSelected] = useState<string | null>(null);
  const [pickedNight, setPickedNight] = useState<string | null>(null);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  const current = plan.sections.find((s) => s.section === selected) ?? plan.sections[0];
  if (!current) return null;
  // Decided blocks the plan no longer uses: every cancelled one, and a late
  // grant or a move that left no work fitting. Still shown, so the decision
  // stays visible and can be undone.
  const inPlan = new Set(current.blocks.map((b) => b.block_id));
  const offPlan = ops.decisions.filter((d) => d.section === current.section && !inPlan.has(d.block_id));

  const nights = Array.from(
    new Set([...current.blocks.map((b) => nightKey(b.start_time)), ...offPlan.map((d) => nightKey(decidedStart(d)))])
  ).sort();
  const tonight = nightKey(new Date());
  const night = pickedNight && nights.includes(pickedNight) ? pickedNight : nights.includes(tonight) ? tonight : nights[0];
  const planDays = planDaysOf(plan.sections);

  const cards = [
    ...current.blocks
      .filter((b) => nightKey(b.start_time) === night)
      .map((b) => ({ block: b, decision: ops.decisionOf.get(b.block_id), start: b.start_time })),
    ...offPlan.filter((d) => nightKey(decidedStart(d)) === night).map((d) => ({ block: null, decision: d, start: decidedStart(d) })),
  ].sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());

  // A moved block lands on another night; follow it there so it stays in view.
  const decide = (id: string, kind: BlockDecisionKind, opts: DecideOptions = {}) =>
    ops.decide(current, id, kind, opts).then((ok) => {
      if (ok && kind === "rescheduled" && opts.newStart) setPickedNight(nightKey(opts.newStart));
    });

  const undo = (id: string) => {
    const d = ops.decisionOf.get(id);
    ops.undo(current, id).then((ok) => {
      if (ok && d?.decision === "rescheduled") setPickedNight(nightKey(d.planned_start));
    });
  };

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Control office — block decisions</h1>
      <p style={{ fontSize: 13, color: "#475569", marginTop: 4, maxWidth: 780 }}>
        Record what happens to each planned block: granted, granted late, rescheduled to another time, or
        cancelled. Every decision is saved and the week's plan is re-optimised at once — a late grant shortens
        the block, a move re-plans the work around its new time, a cancelled block's work goes to other blocks
        if it fits. Nothing else moves unless it has to.
      </p>
      <div
        style={{
          fontSize: 12,
          color: "#475569",
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: 6,
          padding: "8px 12px",
          margin: "12px 0 16px",
        }}
      >
        Granting records the go-ahead but does not lock the work inside the block: a later report or
        cancellation can still move it. The plan does not check a moved block against train running or
        other blocks — check live running on <Link to="/traffic">Corridor Traffic</Link> before deciding.
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Section</span>
        {plan.sections.map((s) => (
          <button
            key={s.section}
            onClick={() => {
              setSelected(s.section);
              ops.setMessage(null);
            }}
            style={{
              fontSize: 12,
              padding: "4px 11px",
              borderRadius: 5,
              cursor: "pointer",
              border: s.section === current.section ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: s.section === current.section ? "#0f172a" : "white",
              color: s.section === current.section ? "white" : "#475569",
            }}
          >
            {s.section}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 10, alignItems: "center", margin: "12px 0 16px", flexWrap: "wrap" }}>
        {nights.length > 0 && (
          <select
            value={night}
            onChange={(e) => setPickedNight(e.target.value)}
            style={{ fontSize: 12, padding: "4px 6px", border: "1px solid #cbd5e1", borderRadius: 5 }}
          >
            {nights.map((n) => (
              <option key={n} value={n}>
                {n === tonight ? "Tonight — " : ""}
                {nightLabel(n)}
              </option>
            ))}
          </select>
        )}
        {nights.length > 0 && !nights.includes(tonight) && (
          <span style={{ fontSize: 11, color: "#94a3b8" }}>
            No blocks tonight — this week's plan covers the nights of {dateLabel(nights[0])} to{" "}
            {dateLabel(nights[nights.length - 1])}
          </span>
        )}
      </div>

      {ops.message && <DecisionMessageBox message={ops.message} />}

      {cards.length === 0 ? (
        <p style={{ fontSize: 13, color: "#94a3b8" }}>No blocks planned on {current.section} this week.</p>
      ) : (
        cards.map(({ block, decision }) => {
          const id = block?.block_id ?? decision!.block_id;
          return (
            <BlockCard
              key={`${id}-${decision?.decided_at ?? "none"}`}
              block={block}
              decision={decision}
              section={current}
              planDays={planDays}
              busy={ops.busy}
              onDecide={(kind, opts) => decide(id, kind, opts)}
              onUndo={() => undo(id)}
            />
          );
        })
      )}
    </div>
  );
}
