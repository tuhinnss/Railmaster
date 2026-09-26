import { useState } from "react";
import { runWhatIf } from "../api/client";
import SafetyChecks from "../components/SafetyChecks";
import { BLOCK_TYPE_LABELS } from "../constants/colors";
import { DEFAULT_BLOCK_TYPE, DEFECT_TYPES } from "../constants/defects";
import { usePlan } from "../context/PlanContext";
import type {
  BlockType,
  Department,
  Disruption,
  SectionPlanResult,
  SeverityCode,
  TaskChangeKind,
  WhatIfResponse,
} from "../types";
import { hhmm } from "../utils/time";

const CHANGE_LABELS: Record<TaskChangeKind, { text: string; color: string }> = {
  dropped: { text: "Dropped", color: "#dc2626" },
  new_unscheduled: { text: "New · not placed", color: "#dc2626" },
  new_scheduled: { text: "New · placed", color: "#15803d" },
  moved: { text: "Moved", color: "#475569" },
  added: { text: "Now placed", color: "#15803d" },
};

// Moving a block is a control-office decision (Block Decisions page); the
// scenario form offers the other three.
type Kind = Exclude<Disruption["kind"], "move_block">;

function describe(d: Disruption): string {
  if (d.kind === "cancel_block") return `Cancel ${d.block_id}`;
  if (d.kind === "curtail_block") return `${d.block_id} granted ${d.minutes_lost} min late`;
  if (d.kind === "move_block") return `${d.block_id} moved to ${d.new_start.replace("T", " ")}`;
  return `New sev-${d.severity_code ?? "A"} ${d.department} defect (${d.defect_type.replaceAll("_", " ")}) at km ${d.km_from}–${d.km_to} in ${d.section}, ${d.est_duration_min} min ${BLOCK_TYPE_LABELS[d.block_type_required].toLowerCase()}`;
}

const fieldStyle = { fontSize: 12, padding: "4px 6px", border: "1px solid #cbd5e1", borderRadius: 4 } as const;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 11, color: "#64748b" }}>
      {label}
      {children}
    </label>
  );
}

function DisruptionForm({ sections, onAdd }: { sections: SectionPlanResult[]; onAdd: (d: Disruption) => void }) {
  const [kind, setKind] = useState<Kind>("cancel_block");
  const allBlocks = sections.flatMap((s) => s.blocks);
  const [blockId, setBlockId] = useState(allBlocks[0]?.block_id ?? "");
  const [minutesLost, setMinutesLost] = useState(60);

  const [section, setSection] = useState(sections[0]?.section ?? "");
  const sec = sections.find((s) => s.section === section);
  const mid = sec ? (sec.km_start + sec.km_end) / 2 : 0;
  const [department, setDepartment] = useState<Department>("Engineering");
  const [defectType, setDefectType] = useState(DEFECT_TYPES.Engineering[0]);
  const [kmFrom, setKmFrom] = useState(mid);
  const [kmTo, setKmTo] = useState(mid + 0.3);
  const [duration, setDuration] = useState(120);
  const [blockType, setBlockType] = useState<BlockType>("traffic");
  const [severity, setSeverity] = useState<SeverityCode>("A");

  const pickSection = (name: string) => {
    setSection(name);
    const s = sections.find((x) => x.section === name);
    if (s) {
      const m = Math.round(((s.km_start + s.km_end) / 2) * 100) / 100;
      setKmFrom(m);
      setKmTo(Math.round((m + 0.3) * 100) / 100);
    }
  };

  const pickDepartment = (d: Department) => {
    setDepartment(d);
    setDefectType(DEFECT_TYPES[d][0]);
    setBlockType(DEFAULT_BLOCK_TYPE[d]);
  };

  const submit = () => {
    if (kind === "cancel_block") onAdd({ kind, block_id: blockId });
    else if (kind === "curtail_block") onAdd({ kind, block_id: blockId, minutes_lost: minutesLost });
    else
      onAdd({
        kind,
        section,
        department,
        defect_type: defectType,
        km_from: kmFrom,
        km_to: kmTo,
        severity_code: severity,
        est_duration_min: duration,
        block_type_required: blockType,
      });
  };

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 14 }}>
      <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
        {(
          [
            ["cancel_block", "Block cancelled"],
            ["curtail_block", "Block granted late"],
            ["urgent_defect", "New urgent defect"],
          ] as [Kind, string][]
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setKind(k)}
            style={{
              fontSize: 12,
              padding: "4px 11px",
              borderRadius: 5,
              cursor: "pointer",
              border: k === kind ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: k === kind ? "#0f172a" : "white",
              color: k === kind ? "white" : "#475569",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        {kind !== "urgent_defect" && (
          <Field label="Block (scheduled blocks only — cancelling an unused one changes nothing)">
            <select value={blockId} onChange={(e) => setBlockId(e.target.value)} style={fieldStyle}>
              {sections.map((s) => (
                <optgroup key={s.section} label={s.section}>
                  {s.blocks.map((b) => (
                    <option key={b.block_id} value={b.block_id}>
                      {b.block_id} · {new Date(b.start_time).toLocaleDateString(undefined, { weekday: "short" })}{" "}
                      {hhmm(b.start_time)}–{hhmm(b.end_time)} · {b.task_ids.length} task(s)
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </Field>
        )}
        {kind === "curtail_block" && (
          <Field label="Minutes lost at the start">
            <input
              type="number"
              min={15}
              step={15}
              value={minutesLost}
              onChange={(e) => setMinutesLost(Number(e.target.value))}
              style={{ ...fieldStyle, width: 80 }}
            />
          </Field>
        )}
        {kind === "urgent_defect" && (
          <>
            <Field label="Section">
              <select value={section} onChange={(e) => pickSection(e.target.value)} style={fieldStyle}>
                {sections.map((s) => (
                  <option key={s.section} value={s.section}>
                    {s.section} (km {s.km_start}–{s.km_end})
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Department">
              <select value={department} onChange={(e) => pickDepartment(e.target.value as Department)} style={fieldStyle}>
                {(Object.keys(DEFECT_TYPES) as Department[]).map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
            <Field label="Defect">
              <select value={defectType} onChange={(e) => setDefectType(e.target.value)} style={fieldStyle}>
                {DEFECT_TYPES[department].map((t) => (
                  <option key={t} value={t}>
                    {t.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Severity">
              <select value={severity} onChange={(e) => setSeverity(e.target.value as SeverityCode)} style={fieldStyle}>
                <option value="A">A — safety-critical</option>
                <option value="B">B — major</option>
                <option value="C">C — minor</option>
              </select>
            </Field>
            <Field label="Km from">
              <input type="number" step={0.1} value={kmFrom} onChange={(e) => setKmFrom(Number(e.target.value))} style={{ ...fieldStyle, width: 80 }} />
            </Field>
            <Field label="Km to">
              <input type="number" step={0.1} value={kmTo} onChange={(e) => setKmTo(Number(e.target.value))} style={{ ...fieldStyle, width: 80 }} />
            </Field>
            <Field label="Work needed (min)">
              <input type="number" min={30} step={30} value={duration} onChange={(e) => setDuration(Number(e.target.value))} style={{ ...fieldStyle, width: 80 }} />
            </Field>
            <Field label="Block type needed">
              <select value={blockType} onChange={(e) => setBlockType(e.target.value as BlockType)} style={fieldStyle}>
                {(Object.keys(BLOCK_TYPE_LABELS) as BlockType[]).map((t) => (
                  <option key={t} value={t}>
                    {BLOCK_TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
            </Field>
          </>
        )}
        <button onClick={submit} style={{ fontSize: 12, padding: "5px 12px", cursor: "pointer" }}>
          Add to scenario
        </button>
      </div>
    </div>
  );
}

function Delta({ before, after, higherIsBetter = true }: { before: number; after: number; higherIsBetter?: boolean }) {
  const diff = after - before;
  if (diff === 0) return <span style={{ color: "#94a3b8" }}> (no change)</span>;
  const worse = higherIsBetter ? diff < 0 : diff > 0;
  return (
    <span style={{ color: worse ? "#dc2626" : "#15803d", fontWeight: 600 }}>
      {" "}
      ({diff > 0 ? "+" : ""}
      {diff})
    </span>
  );
}

function Result({ result }: { result: WhatIfResponse }) {
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 12, color: "#475569", marginBottom: 10 }}>
        Replanned in <strong>{result.replan_seconds.toFixed(3)} s</strong> — measured wall time of Stage A, Stage B,
        validator and explanations for the affected section(s).
      </div>

      <ul style={{ fontSize: 12.5, paddingLeft: 18, margin: "0 0 14px" }}>
        {result.applied.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 18 }}>
        <thead>
          <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
            <th style={{ padding: "5px 8px", fontWeight: 600 }}>Section</th>
            <th style={{ padding: "5px 8px", fontWeight: 600 }}>Tasks scheduled</th>
            <th style={{ padding: "5px 8px", fontWeight: 600 }}>Blocks opened</th>
            <th style={{ padding: "5px 8px", fontWeight: 600 }}>Blocks saved by merging</th>
          </tr>
        </thead>
        <tbody>
          {result.sections.map(({ section, before, after }) => (
            <tr key={section} style={{ borderTop: "1px solid #f1f5f9" }}>
              <td style={{ padding: "7px 8px", fontWeight: 600 }}>{section}</td>
              <td style={{ padding: "7px 8px" }}>
                {before.scheduled_count}/{before.task_count} → {after.scheduled_count}/{after.task_count}
                <Delta before={before.scheduled_count} after={after.scheduled_count} />
              </td>
              <td style={{ padding: "7px 8px" }}>
                {before.blocks_opened} → {after.blocks_opened}
              </td>
              <td style={{ padding: "7px 8px" }}>
                {before.blocks_saved} → {after.blocks_saved}
                <Delta before={before.blocks_saved} after={after.blocks_saved} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 style={{ fontSize: 15 }}>What changed ({result.changes.length})</h2>
      {result.changes.length === 0 ? (
        <p style={{ fontSize: 13, color: "#64748b" }}>
          No task changed block — the disruption still left room for every task that was placed.
        </p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Change</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Task</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Block before → after</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Outcome now</th>
            </tr>
          </thead>
          <tbody>
            {result.changes.map((c) => (
              <tr key={c.task_id} style={{ borderTop: "1px solid #f1f5f9" }}>
                <td style={{ padding: "6px", whiteSpace: "nowrap", fontWeight: 700, color: CHANGE_LABELS[c.change].color }}>
                  {CHANGE_LABELS[c.change].text}
                </td>
                <td style={{ padding: "6px", whiteSpace: "nowrap" }}>
                  {c.task_id}
                  <div style={{ fontSize: 10.5, color: "#94a3b8" }}>{c.section}</div>
                </td>
                <td style={{ padding: "6px", whiteSpace: "nowrap", fontSize: 11.5 }}>
                  {c.block_before ?? "—"} → {c.block_after ?? "—"}
                </td>
                <td style={{ padding: "6px", color: "#475569" }}>{c.reason_after}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: 15, marginTop: 24 }}>Safety checks on the replanned sections</h2>
      {result.sections.map(({ section, after }) => (
        <div key={section} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, margin: "6px 0" }}>{section}</div>
          <SafetyChecks checks={after.safety_checks} />
        </div>
      ))}
    </div>
  );
}

export default function WhatIf() {
  const { plan, loading, error } = usePlan();
  const [scenario, setScenario] = useState<Disruption[]>([]);
  const [result, setResult] = useState<WhatIfResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  const run = () => {
    setRunning(true);
    setRunError(null);
    runWhatIf(scenario)
      .then(setResult)
      .catch((e: Error) => setRunError(e.message))
      .finally(() => setRunning(false));
  };

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>What-if replanning</h1>
      <p style={{ fontSize: 13, color: "#475569", marginTop: 4 }}>
        Disrupt this week's plan, then re-run the full scheduler on the affected sections to see what it does
        about it. Among equally good replans, the scheduler keeps the current plan, so every change listed is
        one the disruption forced.
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
        Scenarios start from the current plan, including field reports and control decisions, and are never
        saved. The published plan and its data stay exactly as they are.
      </div>

      <DisruptionForm sections={plan.sections} onAdd={(d) => setScenario((s) => [...s, d])} />

      <div style={{ marginTop: 14 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: 6 }}>
          Scenario
        </div>
        {scenario.length === 0 ? (
          <p style={{ fontSize: 13, color: "#94a3b8", margin: 0 }}>No disruptions yet — add one above.</p>
        ) : (
          <ol style={{ fontSize: 13, paddingLeft: 20, margin: 0 }}>
            {scenario.map((d, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {describe(d)}{" "}
                <button
                  onClick={() => setScenario((s) => s.filter((_, j) => j !== i))}
                  style={{ fontSize: 11, border: "none", background: "none", color: "#64748b", cursor: "pointer" }}
                >
                  remove
                </button>
              </li>
            ))}
          </ol>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button
            onClick={run}
            disabled={scenario.length === 0 || running}
            style={{ fontSize: 13, padding: "6px 14px", cursor: scenario.length === 0 ? "default" : "pointer" }}
          >
            {running ? "Replanning…" : "Replan"}
          </button>
          <button
            onClick={() => {
              setScenario([]);
              setResult(null);
              setRunError(null);
            }}
            style={{ fontSize: 13, padding: "6px 14px", cursor: "pointer" }}
          >
            Clear
          </button>
        </div>
        {runError && <p style={{ color: "#dc2626", fontSize: 13 }}>{runError}</p>}
      </div>

      {result && <Result result={result} />}
    </div>
  );
}
