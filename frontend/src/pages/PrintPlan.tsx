import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import SafetyChecks from "../components/SafetyChecks";
import { BLOCK_TYPE_LABELS } from "../constants/colors";
import { usePlan } from "../context/PlanContext";
import type { SectionPlanResult, TaskSummary } from "../types";
import { hhmm } from "../utils/time";

// A print-first rendering of the weekly plan: open it, then use the
// browser's Print / Save as PDF. It is deliberately a plain working
// document, not styled as an official railway circular -- the plan comes
// from synthetic defect data and has had no human sign-off, and a page
// that looks sanctioned would say otherwise.
//
// One section per printout (?section=GHY-LMG): each section's programme is
// planned and worked separately, so each gets its own PDF, with its own
// fingerprint and a file name that says which section it is.

const cell = { padding: "4px 6px", border: "1px solid #cbd5e1", verticalAlign: "top" as const };
const head = { ...cell, background: "#f1f5f9", fontWeight: 700, textAlign: "left" as const };

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

function Section({ s }: { s: SectionPlanResult }) {
  const byId = new Map(s.tasks.map((t) => [t.task_id, t]));
  const unscheduled = s.tasks.filter((t) => !t.scheduled);
  const tasksOf = (ids: string[]) => ids.map((id) => byId.get(id)).filter((t): t is TaskSummary => Boolean(t));

  return (
    <section>
      <h2 style={{ fontSize: 15, margin: "0 0 4px", borderBottom: "2px solid #0f172a", paddingBottom: 3 }}>
        {s.section} <span style={{ fontWeight: 400, color: "#475569" }}>· km {s.km_start}–{s.km_end}</span>
      </h2>
      <p style={{ fontSize: 11.5, margin: "4px 0 10px" }}>
        {s.scheduled_count} of {s.task_count} tasks scheduled in {s.blocks_opened} blocks ·{" "}
        {s.blocks_used_without_merging} blocks without merging ({s.blocks_saved} saved) ·{" "}
        {s.ntes_integrated ? "corridor availability enriched from ntes-adapter where data exists" : "fully synthetic"}
      </p>

      <h3 style={{ fontSize: 12, margin: "10px 0 4px", textTransform: "uppercase" }}>Block programme</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 10.5 }}>
        <thead>
          <tr>
            <th style={head}>Date</th>
            <th style={head}>Time</th>
            <th style={head}>Block</th>
            <th style={head}>Type</th>
            <th style={head}>Work (department · task · defect · km · min)</th>
            <th style={head}>Used</th>
          </tr>
        </thead>
        <tbody>
          {s.blocks.map((b) => (
            <tr key={b.block_id} style={{ breakInside: "avoid" }}>
              <td style={cell}>{fmtDate(b.start_time)}</td>
              <td style={{ ...cell, whiteSpace: "nowrap" }}>
                {hhmm(b.start_time)}–{hhmm(b.end_time)}
              </td>
              <td style={cell}>
                {b.block_id}
                {b.data_source === "ntes_live" && " ●"}
                {b.data_source === "added" && " (added)"}
              </td>
              <td style={cell}>{BLOCK_TYPE_LABELS[b.block_type_possible]}</td>
              <td style={cell}>
                {tasksOf(b.task_ids).map((t) => (
                  <div key={t.task_id}>
                    {t.department} · {t.task_id} · {t.defect_type.replaceAll("_", " ")} · km{" "}
                    {t.km_range[0].toFixed(2)}–{t.km_range[1].toFixed(2)} · {t.est_duration_min}
                  </div>
                ))}
              </td>
              <td style={{ ...cell, whiteSpace: "nowrap" }}>
                {b.used_min}/{b.duration_min} min
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {unscheduled.length > 0 && (
        <>
          <h3 style={{ fontSize: 12, margin: "14px 0 4px", textTransform: "uppercase" }}>
            Not scheduled this week ({unscheduled.length})
          </h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 10.5 }}>
            <thead>
              <tr>
                <th style={head}>Task</th>
                <th style={head}>Sev.</th>
                <th style={head}>Needs</th>
                <th style={head}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {unscheduled.map((t) => (
                <tr key={t.task_id} style={{ breakInside: "avoid" }}>
                  <td style={cell}>
                    {t.task_id} · {t.department}
                  </td>
                  <td style={cell}>
                    {t.severity_code}
                    {t.days_overdue > 0 ? `, ${t.days_overdue}d overdue` : ""}
                  </td>
                  <td style={{ ...cell, whiteSpace: "nowrap" }}>
                    {t.est_duration_min} min {BLOCK_TYPE_LABELS[t.block_type_required].toLowerCase()}
                  </td>
                  <td style={cell}>{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Kept together so the heading never strands at the foot of a page. */}
      <div style={{ breakInside: "avoid" }}>
        <h3 style={{ fontSize: 12, margin: "14px 0 4px", textTransform: "uppercase" }}>Safety checks</h3>
        <SafetyChecks checks={s.safety_checks} />
      </div>
    </section>
  );
}

export default function PrintPlan() {
  const { plan, loading, error } = usePlan();
  const [params, setParams] = useSearchParams();
  const section = plan?.sections.find((x) => x.section === params.get("section")) ?? plan?.sections[0];
  const starts = section ? section.blocks.map((b) => b.start_time).sort() : [];

  // The browser offers document.title as the PDF's file name, so each
  // section saves as its own file instead of overwriting the last one.
  useEffect(() => {
    if (!section) return;
    const previous = document.title;
    const week = starts.length > 0 ? ` week of ${starts[0].slice(0, 10)}` : "";
    document.title = `Block programme ${section.section}${week}`;
    return () => {
      document.title = previous;
    };
  }, [section?.section, starts[0]]);

  if (loading) return <p>Loading…</p>;
  if (error) return <p style={{ color: "#dc2626" }}>Failed to load plan: {error}</p>;
  if (!plan || !section) return null;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", color: "#0f172a" }}>
      <style>{"@media print { .no-print { display: none !important; } @page { margin: 14mm; } }"}</style>

      <div className="no-print" style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b" }}>Section</span>
        {plan.sections.map((x) => (
          <button
            key={x.section}
            onClick={() => setParams({ section: x.section })}
            style={{
              fontSize: 12,
              padding: "4px 11px",
              borderRadius: 5,
              cursor: "pointer",
              border: x.section === section.section ? "1px solid #0f172a" : "1px solid #cbd5e1",
              background: x.section === section.section ? "#0f172a" : "white",
              color: x.section === section.section ? "white" : "#475569",
            }}
          >
            {x.section}
          </button>
        ))}
        <button onClick={() => window.print()} style={{ fontSize: 13, padding: "6px 14px", cursor: "pointer", marginLeft: "auto" }}>
          Print / Save as PDF
        </button>
      </div>

      <h1 style={{ fontSize: 19, margin: 0 }}>Weekly maintenance block programme — {section.section}</h1>
      <p style={{ fontSize: 12, margin: "4px 0 0", color: "#334155" }}>
        {starts.length > 0 && (
          <>
            Blocks from {fmtDate(starts[0])} to {fmtDate(starts[starts.length - 1])} ·{" "}
          </>
        )}
        generated {new Date(plan.generated_at).toLocaleString()}
      </p>

      <div style={{ border: "1px solid #94a3b8", borderRadius: 4, padding: "8px 10px", margin: "12px 0", fontSize: 11 }}>
        <strong>Prototype output — not an operational document.</strong> Railmaster (SIH26027 prototype). Defect
        and block data come from a seeded synthetic generator. Blocks marked ● take their expected train impact from
        ntes-adapter's NTES-derived availability: a frequency count over nights the adapter has observed, which are
        either measured by live polling or illustrative seed values, depending on how the adapter is run. Blocks
        marked (added) were added by hand for work that didn't fit and have no train-impact figure. No part of this
        plan has been reviewed or approved by anyone.
      </div>

      <p style={{ fontSize: 10.5, margin: "0 0 18px", color: "#334155" }}>
        Fingerprint of this section's plan (SHA-256):{" "}
        <code style={{ fontSize: 10, wordBreak: "break-all" }}>{section.fingerprint}</code>
        <br />
        Identifies exactly what this page shows — which task is in which block, and when those blocks run. The same
        data produces the same value. It is not a signature.
      </p>

      <Section s={section} />
    </div>
  );
}
