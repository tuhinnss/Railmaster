// Shared by the pages where the control office acts on blocks (Overview's
// block map and Block Decisions): date keys, labels, and the plain-language
// account of what a decision did to the plan.

import type { BlockDecision, BlockDecisionKind, SectionPlanResult } from "../types";
import { hhmm } from "./time";

const pad = (n: number) => String(n).padStart(2, "0");

// Local calendar day, YYYY-MM-DD.
export function dayKey(time: string | Date): string {
  const d = new Date(time);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// A control office works in nights, not calendar days: a block at 00:30 on
// Tuesday belongs to Monday night. Keyed by the evening's date, noon to noon.
export function nightKey(time: string | Date): string {
  return dayKey(new Date(new Date(time).getTime() - 12 * 3_600_000));
}

export function dateLabel(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

export function nightLabel(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  const morning = new Date(y, m - 1, d + 1).toLocaleDateString(undefined, { weekday: "short" });
  return `Night of ${dateLabel(key)} → ${morning}`;
}

export function span(start: string, end: string): string {
  return `${dateLabel(dayKey(start))}, ${hhmm(start)}–${hhmm(end)}`;
}

export const DECISION_STATUS: Record<BlockDecisionKind | "pending", { text: string; color: string; bg: string }> = {
  pending: { text: "Awaiting decision", color: "#475569", bg: "#f1f5f9" },
  granted: { text: "Granted", color: "#15803d", bg: "#dcfce7" },
  granted_late: { text: "Granted late", color: "#b45309", bg: "#fef3c7" },
  rescheduled: { text: "Rescheduled", color: "#4338ca", bg: "#e0e7ff" },
  cancelled: { text: "Cancelled", color: "#b91c1c", bg: "#fee2e2" },
};

// Where a decided block now sits: its new time if it was moved, else its
// planned time. Used for blocks the plan no longer uses.
export function decidedStart(d: BlockDecision): string {
  return d.decision === "rescheduled" && d.new_start ? d.new_start : d.planned_start;
}

export function decidedEnd(d: BlockDecision): string {
  return d.decision === "rescheduled" && d.new_end ? d.new_end : d.planned_end;
}

// Days a block can be moved to: the plan week, first to last planned day.
// The backend holds reschedules to the same span.
export function planDaysOf(sections: SectionPlanResult[]): string[] {
  const planned = sections.flatMap((s) => s.blocks.map((b) => dayKey(b.start_time))).sort();
  if (planned.length === 0) return [];
  const [y, m, d] = planned[0].split("-").map(Number);
  const days: string[] = [];
  for (let i = 0; ; i++) {
    const k = dayKey(new Date(y, m - 1, d + i));
    days.push(k);
    if (k >= planned[planned.length - 1]) break;
  }
  return days;
}

// What a decision did to the section's plan, task by task. Only tasks whose
// block changed are listed.
export function describeChanges(before: SectionPlanResult | undefined, after: SectionPlanResult | undefined): string[] {
  if (!before || !after) return [];
  const was = new Map(before.tasks.map((t) => [t.task_id, t.block_id]));
  const blocks = new Map(after.blocks.map((b) => [b.block_id, b]));
  const lines: string[] = [];
  for (const t of after.tasks) {
    const prev = was.get(t.task_id) ?? null;
    if (prev === t.block_id) continue;
    const b = t.block_id ? blocks.get(t.block_id) : undefined;
    const where = b ? `${b.block_id} (${new Date(b.start_time).toLocaleDateString(undefined, { weekday: "short" })} ${hhmm(b.start_time)})` : "";
    if (!t.block_id) lines.push(`${t.task_id} no longer fits anywhere this week — now unscheduled.`);
    else if (!prev) lines.push(`${t.task_id} now fits: ${where}.`);
    else lines.push(`${t.task_id} moved from ${prev} to ${where}.`);
  }
  return lines;
}
