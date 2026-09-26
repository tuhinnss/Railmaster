import { useEffect, useState } from "react";
import { addBlock, decideBlock, fetchAddedBlocks, fetchDecisions, removeAddedBlock, undoDecision } from "../api/client";
import { usePlan } from "../context/PlanContext";
import type { AddedBlock, BlockDecision, BlockDecisionKind, SectionPlanResult, TaskSummary } from "../types";
import { describeChanges, span } from "../utils/blockDecisions";

export type DecideOptions = { minutesLost?: number; newStart?: string; durationMin?: number };

export interface DecisionMessage {
  head: string;
  lines: string[];
  error?: boolean;
}

function headFor(kind: BlockDecisionKind, opts: DecideOptions): string {
  if (kind === "granted") return "granted.";
  if (kind === "cancelled") return "cancelled — removed from the plan.";
  if (kind === "granted_late") return `granted ${opts.minutesLost} min late.`;
  const start = opts.newStart ?? "";
  const end = new Date(new Date(start).getTime() + (opts.durationMin ?? 0) * 60_000).toISOString();
  return `moved to ${span(start, end)}.`;
}

// A block added for work that didn't fit, and whether the work got into it.
function addedHead(block: AddedBlock, after: SectionPlanResult | undefined): string {
  const head = `${block.block_id} added for ${block.for_task}, ${span(block.start_time, block.end_time)}.`;
  const task = after?.tasks.find((t) => t.task_id === block.for_task);
  if (!task || task.scheduled) return head;
  return `${head} ${block.for_task} still doesn't fit — ${task.reason.replace(/^Not scheduled: /, "")} The block stays unused until you remove it.`;
}

// Control-office actions on blocks -- decisions, and blocks added for work
// that didn't fit: the saved lists, and actions that save a change, refetch
// the re-optimised plan, and say which tasks it moved. Each action resolves
// to whether it succeeded.
export function useBlockDecisions() {
  const { reload } = usePlan();
  const [decisions, setDecisions] = useState<BlockDecision[]>([]);
  const [added, setAdded] = useState<AddedBlock[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<DecisionMessage | null>(null);

  useEffect(() => {
    Promise.all([fetchDecisions(), fetchAddedBlocks()])
      .then(([list, blocks]) => {
        setDecisions(list);
        setAdded(blocks);
      })
      .catch((e: Error) => setMessage({ head: `Could not load decisions: ${e.message}`, lines: [], error: true }));
  }, []);

  // `head` words the outcome once the change's result and the section's new
  // plan are known.
  const run = <T,>(
    before: SectionPlanResult,
    change: () => Promise<T>,
    head: (result: T, after: SectionPlanResult | undefined) => string
  ) => {
    setBusy(true);
    setMessage(null);
    return change()
      .then((result) =>
        Promise.all([reload(), fetchDecisions(), fetchAddedBlocks()]).then(([next, list, blocks]) => {
          setDecisions(list);
          setAdded(blocks);
          const after = next.sections.find((s) => s.section === before.section);
          setMessage({ head: head(result, after), lines: describeChanges(before, after) });
          return true;
        })
      )
      .catch((e: Error) => {
        setMessage({ head: e.message, lines: [], error: true });
        return false;
      })
      .finally(() => setBusy(false));
  };

  return {
    decisions,
    decisionOf: new Map(decisions.map((d) => [d.block_id, d])),
    added,
    addedOf: new Map(added.map((a) => [a.block_id, a])),
    busy,
    message,
    setMessage,
    decide: (before: SectionPlanResult, blockId: string, kind: BlockDecisionKind, opts: DecideOptions = {}) =>
      run(before, () => decideBlock(blockId, kind, opts), () => `${blockId}: ${headFor(kind, opts)}`),
    undo: (before: SectionPlanResult, blockId: string) =>
      run(before, () => undoDecision(blockId), () => `${blockId}: decision undone.`),
    add: (before: SectionPlanResult, task: TaskSummary, start: string, durationMin: number) =>
      run(before, () => addBlock(task.task_id, start, durationMin), addedHead),
    removeAdded: (before: SectionPlanResult, blockId: string) =>
      run(before, () => removeAddedBlock(blockId), () => `${blockId} removed.`),
  };
}
