import { useEffect, useState } from "react";
import { decideBlock, fetchDecisions, undoDecision } from "../api/client";
import { usePlan } from "../context/PlanContext";
import type { BlockDecision, BlockDecisionKind, PlanResponse, SectionPlanResult } from "../types";
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

// Control-office decisions on blocks: the saved list, and actions that save
// a decision, refetch the re-optimised plan, and say which tasks it moved.
// Each action resolves to whether it succeeded.
export function useBlockDecisions() {
  const { reload } = usePlan();
  const [decisions, setDecisions] = useState<BlockDecision[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<DecisionMessage | null>(null);

  useEffect(() => {
    fetchDecisions()
      .then(setDecisions)
      .catch((e: Error) => setMessage({ head: `Could not load decisions: ${e.message}`, lines: [], error: true }));
  }, []);

  const run = (before: SectionPlanResult, blockId: string, head: string, change: () => Promise<unknown>) => {
    setBusy(true);
    setMessage(null);
    return change()
      .then(() => Promise.all([reload(), fetchDecisions()]))
      .then(([next, list]: [PlanResponse, BlockDecision[]]) => {
        setDecisions(list);
        const lines = describeChanges(before, next.sections.find((s) => s.section === before.section));
        setMessage({ head: `${blockId}: ${head}`, lines });
        return true;
      })
      .catch((e: Error) => {
        setMessage({ head: e.message, lines: [], error: true });
        return false;
      })
      .finally(() => setBusy(false));
  };

  return {
    decisions,
    decisionOf: new Map(decisions.map((d) => [d.block_id, d])),
    busy,
    message,
    setMessage,
    decide: (before: SectionPlanResult, blockId: string, kind: BlockDecisionKind, opts: DecideOptions = {}) =>
      run(before, blockId, headFor(kind, opts), () => decideBlock(blockId, kind, opts)),
    undo: (before: SectionPlanResult, blockId: string) =>
      run(before, blockId, "decision undone.", () => undoDecision(blockId)),
  };
}
