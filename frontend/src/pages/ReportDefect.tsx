import { useEffect, useState } from "react";
import { fetchReports, submitReport, withdrawReport } from "../api/client";
import DepartmentBadge from "../components/DepartmentBadge";
import SeverityBadge from "../components/SeverityBadge";
import { BLOCK_TYPE_LABELS } from "../constants/colors";
import { DEFAULT_BLOCK_TYPE, DEFECT_TYPES } from "../constants/defects";
import { usePlan } from "../context/PlanContext";
import type { BlockType, DefectReport, Department, PlanResponse, SeverityCode } from "../types";
import { hhmm } from "../utils/time";

const fieldStyle = { fontSize: 13, padding: "5px 7px", border: "1px solid #cbd5e1", borderRadius: 4 } as const;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "#64748b" }}>
      {label}
      {children}
    </label>
  );
}

function when(time: string): string {
  const d = new Date(time);
  return `${d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}, ${hhmm(d)}`;
}

// Where a report stands in the plan right now, in one line.
function standing(plan: PlanResponse | null, reportId: string): { text: string; placed: boolean } {
  for (const section of plan?.sections ?? []) {
    const task = section.tasks.find((t) => t.task_id === reportId);
    if (!task) continue;
    const block = task.block_id ? section.blocks.find((b) => b.block_id === task.block_id) : undefined;
    if (!block) return { text: `Not scheduled this week. ${task.reason}`, placed: false };
    const others = block.task_ids.length - 1;
    return {
      text: `Scheduled in ${block.block_id}, ${when(block.start_time)}–${hhmm(block.end_time)}${
        others > 0 ? `, sharing the block with ${others} other task${others === 1 ? "" : "s"}` : ""
      }.`,
      placed: true,
    };
  }
  return { text: "Not in the plan yet.", placed: false };
}

export default function ReportDefect() {
  const { plan, loading, error, reload } = usePlan();
  const [reports, setReports] = useState<DefectReport[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  const [section, setSection] = useState<string | null>(null);
  const [department, setDepartment] = useState<Department>("Engineering");
  const [defectType, setDefectType] = useState("");
  const [severity, setSeverity] = useState<SeverityCode>("B");
  const [kmFrom, setKmFrom] = useState<number | null>(null);
  const [kmTo, setKmTo] = useState<number | null>(null);
  const [duration, setDuration] = useState(60);
  const [blockType, setBlockType] = useState<BlockType>("traffic");
  const [description, setDescription] = useState("");
  const [reportedBy, setReportedBy] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastReport, setLastReport] = useState<string | null>(null);

  useEffect(() => {
    fetchReports()
      .then(setReports)
      .catch((e: Error) => setListError(e.message));
  }, []);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan) return null;

  const current = plan.sections.find((s) => s.section === section) ?? plan.sections[0];
  if (!current) return null;
  const mid = Math.round(((current.km_start + current.km_end) / 2) * 10) / 10;
  const from = kmFrom ?? mid;
  const to = kmTo ?? Math.round((mid + 0.3) * 10) / 10;

  const pickSection = (name: string) => {
    setSection(name);
    setKmFrom(null); // back to the new section's midpoint
    setKmTo(null);
  };

  const pickDepartment = (d: Department) => {
    setDepartment(d);
    setBlockType(DEFAULT_BLOCK_TYPE[d]);
  };

  const submit = () => {
    if (!defectType.trim()) {
      setSubmitError("Say what the defect is.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    submitReport({
      section: current.section,
      department,
      defect_type: defectType,
      km_from: from,
      km_to: to,
      severity_code: severity,
      est_duration_min: duration,
      block_type_required: blockType,
      description: description.trim(),
      reported_by: reportedBy.trim(),
    })
      .then((created) =>
        Promise.all([reload(), fetchReports()]).then(([, list]) => {
          setReports(list);
          setLastReport(created.report_id);
          setDefectType("");
          setDescription("");
        })
      )
      .catch((e: Error) => setSubmitError(e.message))
      .finally(() => setSubmitting(false));
  };

  const withdraw = (reportId: string) => {
    withdrawReport(reportId)
      .then(() => Promise.all([reload(), fetchReports()]))
      .then(([, list]) => {
        setReports(list);
        if (lastReport === reportId) setLastReport(null);
      })
      .catch((e: Error) => setListError(e.message));
  };

  const outcome = lastReport ? standing(plan, lastReport) : null;

  return (
    <div>
      <h1 style={{ fontSize: 20 }}>Report a defect</h1>
      <p style={{ fontSize: 13, color: "#475569", marginTop: 4, maxWidth: 760 }}>
        Report a defect found on the line. It joins that section's maintenance backlog straight away and the
        week's plan is re-optimised around it; other work moves only if it has to.
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
        Reports are saved and marked <strong>REPORTED</strong> on every page, so they are never mixed up with the
        generated backlog. Severity sets the due date: A today, B within 7 days, C within 30 days. That rule is a
        prototype assumption, not a railway standard.
      </div>

      <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16 }}>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Field label="Section">
            <select value={current.section} onChange={(e) => pickSection(e.target.value)} style={fieldStyle}>
              {plan.sections.map((s) => (
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
            <input
              value={defectType}
              maxLength={80}
              placeholder="e.g. rail fracture risk"
              onChange={(e) => setDefectType(e.target.value)}
              style={{ ...fieldStyle, width: 230 }}
            />
          </Field>
          <Field label="Severity">
            <select value={severity} onChange={(e) => setSeverity(e.target.value as SeverityCode)} style={fieldStyle}>
              <option value="A">A — safety-critical</option>
              <option value="B">B — major</option>
              <option value="C">C — minor</option>
            </select>
          </Field>
        </div>

        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end", marginTop: 14 }}>
          <Field label="Km from">
            <input type="number" step={0.1} value={from} onChange={(e) => setKmFrom(Number(e.target.value))} style={{ ...fieldStyle, width: 90 }} />
          </Field>
          <Field label="Km to">
            <input type="number" step={0.1} value={to} onChange={(e) => setKmTo(Number(e.target.value))} style={{ ...fieldStyle, width: 90 }} />
          </Field>
          <Field label="Work needed (min)">
            <input type="number" min={15} step={15} value={duration} onChange={(e) => setDuration(Number(e.target.value))} style={{ ...fieldStyle, width: 90 }} />
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
          <Field label="Reported by (optional)">
            <input value={reportedBy} maxLength={80} onChange={(e) => setReportedBy(e.target.value)} style={{ ...fieldStyle, width: 170 }} />
          </Field>
        </div>

        <div style={{ marginTop: 14 }}>
          <Field label="What was found (optional)">
            <textarea
              value={description}
              maxLength={500}
              rows={2}
              onChange={(e) => setDescription(e.target.value)}
              style={{ ...fieldStyle, width: "100%", maxWidth: 640, fontFamily: "inherit", resize: "vertical" }}
            />
          </Field>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 14 }}>
          <button onClick={submit} disabled={submitting} style={{ fontSize: 13, padding: "6px 16px", cursor: "pointer" }}>
            {submitting ? "Submitting…" : "Submit report"}
          </button>
          {submitError && <span style={{ color: "#dc2626", fontSize: 13 }}>{submitError}</span>}
        </div>
      </div>

      {lastReport && outcome && (
        <div
          style={{
            marginTop: 16,
            border: `1px solid ${outcome.placed ? "#86efac" : "#fca5a5"}`,
            background: outcome.placed ? "#f0fdf4" : "#fef2f2",
            borderRadius: 8,
            padding: "10px 14px",
            fontSize: 13,
          }}
        >
          <strong>{lastReport}</strong> added to the backlog. {outcome.text}
        </div>
      )}

      <h2 style={{ fontSize: 15, marginTop: 28 }}>Reports ({reports.length})</h2>
      {listError && <p style={{ color: "#dc2626", fontSize: 13 }}>{listError}</p>}
      {reports.length === 0 ? (
        <p style={{ fontSize: 13, color: "#94a3b8" }}>No defects reported yet.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ textAlign: "left", fontSize: 11, color: "#94a3b8" }}>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Report</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Defect</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>Reported</th>
              <th style={{ padding: "5px 6px", fontWeight: 600 }}>In this week's plan</th>
              <th style={{ padding: "5px 6px" }} />
            </tr>
          </thead>
          <tbody>
            {[...reports].reverse().map((r) => {
              const s = standing(plan, r.report_id);
              return (
                <tr key={r.report_id} style={{ borderTop: "1px solid #f1f5f9", verticalAlign: "top" }}>
                  <td style={{ padding: "7px 6px", whiteSpace: "nowrap" }}>
                    <div style={{ fontWeight: 600 }}>{r.report_id}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{r.section}</div>
                  </td>
                  <td style={{ padding: "7px 6px" }}>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                      <DepartmentBadge department={r.department} />
                      <SeverityBadge severity={r.severity_code} />
                      <span>{r.defect_type.replaceAll("_", " ")}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>
                      km {r.km_from}–{r.km_to} · {r.est_duration_min} min · {BLOCK_TYPE_LABELS[r.block_type_required].toLowerCase()} block
                      {r.description && <> · “{r.description}”</>}
                    </div>
                  </td>
                  <td style={{ padding: "7px 6px", whiteSpace: "nowrap", color: "#475569" }}>
                    {when(r.reported_at)}
                    {r.reported_by && <div style={{ fontSize: 11, color: "#94a3b8" }}>by {r.reported_by}</div>}
                  </td>
                  <td style={{ padding: "7px 6px", color: s.placed ? "#15803d" : "#b91c1c" }}>{s.text}</td>
                  <td style={{ padding: "7px 6px", textAlign: "right" }}>
                    <button
                      onClick={() => withdraw(r.report_id)}
                      style={{ fontSize: 11, border: "none", background: "none", color: "#64748b", cursor: "pointer" }}
                    >
                      withdraw
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
