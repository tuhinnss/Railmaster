# Architecture (outline)

Following the prototype build spec (Sep 22, 2026). See that doc for full
rationale; this is just the structural map.

## Data flow

```
app.datagen.generate ──> data/synthetic/{tasks,blocks}.json
                                   │
                                   ▼
                     app/models (MaintenanceTask, BlockOpportunity)
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              prioritizer    CP-SAT scheduler   validator
              (rule-based     (Stage A: single    (section 6
               score)         section; Stage B:   safety rules,
                               cross-dept merge)   run separately
                    │              │               from solver)
                    └──────┬───────┘
                           ▼
                  explainability (section 7)
                           │
                           ▼
                  FastAPI (app/api) ──> React dashboard
```

## Backend layers (`backend/app/`)

- `models/` — the two canonical shapes (`MaintenanceTask`, `BlockOpportunity`)
  every data source converts into, per spec section 2. Nothing downstream
  reads anything else.
- `datagen/` — synthetic data generator (spec section 3). Reproducible via
  `--seed` (default 1, chosen so the overdue share lands in the 15-20%
  target band *and* at least one severity-A overdue task exists, so the
  safety override visibly fires). Sections are limited to the two
  corridors ntes-adapter covers. Run: `python -m app.datagen.generate`
  from `backend/`.
- `scheduling/` — `common.py` (shared constants/delay calc), `compatibility.py`
  (task/block + task/task compatibility, section 6), `config.py` (tunable
  `PriorityWeights`), `prioritizer.py` (rule-based score, section 4),
  `validator.py` (all 6 safety rules, run against solver output, section 6),
  `stage_a.py` (single-section CP-SAT, no merging, section 5), `stage_b.py`
  (merging via beta/gamma consolidation incentive, section 5 — done, worked
  example passes, ~40ms/section), `explain.py` (one-line generated reason
  per task, section 7 — done).

  Known finding: raw "blocks saved" understates what merging does once
  block supply is scarce. On the current two-section dataset (45 tasks,
  40 blocks) GHY-LMG runs Stage A at 17 tasks in 17 blocks and Stage B at
  19 tasks in 16 blocks — merging fits *more work into fewer blocks*,
  which the blocks-saved delta alone (1) doesn't convey. LMG-RNY finds no
  mergeable pair at all (17 in 17 both ways), because task durations often
  consume most of a block's capacity and km ranges are narrow. The worked
  example and a dedicated preference test both confirm the merge logic
  itself is correct.

  Note also that tasks now go unscheduled, so the priority score genuinely
  decides which work loses — under the earlier six-section dataset everything
  fitted and the ranking never bound. Almost all of the shortfall lands on
  `NDLS-GZB`, which by design offers 40% of the baseline window supply
  (`BLOCK_SUPPLY_FACTOR`): 7 of 15 tasks scheduled there against 20 of 21 on
  `GHY-LMG`.
- `planning.py` — the per-section pipeline (Stage A for comparison, Stage B,
  validator, explanations, safety-check summary) assembled into API shapes,
  plus the plan fingerprint and what-if replanning. Shared by the weekly
  plan and what-if so both run identical steps. What-if disruptions apply
  to copies of the loaded data and are never persisted. `plan_current`
  builds the plan every page shows: fixture data plus field reports plus
  control decisions, with touched sections replanned against the fixture
  plan as the tie-break baseline.
- `operations.py` — the only persisted user input: defects reported on
  the Report Defect page and control-office decisions on planned blocks
  (granted / granted late / rescheduled / cancelled), stored as JSON
  under `data/operations/`. Reported defects become tasks with
  `data_source="reported"`; decisions become the same `CancelBlock` /
  `CurtailBlock` / `MoveBlock` disruptions what-if uses.
- `api/` — FastAPI routers exposing tasks, blocks, generated plans,
  what-if replans, and field reports / control decisions
  (`/api/operations`) to the dashboard.
- `ntes_bridge.py` — optional enrichment layer connecting to the separate
  `ntes-adapter/` service (real NTES-derived predicted-availability data
  and real captured train boards, see its own README). For the
  NTES-integrated sections
  (`GHY-LMG`, `LMG-RNY`, per `datagen/reference_data.NTES_INTEGRATED_SECTIONS`
  — currently every configured section, but kept as a separate list so a
  future section without a real source can't silently claim one),
  a block's `expected_train_impact` is overwritten with
  `1 - predicted_availability` when the block's start time falls in a
  window ntes-adapter has real data for; every other section stays
  purely synthetic. Falls back silently to synthetic values if the
  adapter is unreachable or has no data yet — this is enrichment, not a
  hard dependency. Wired into `data_access.load_blocks()`. Also tags
  the block's `data_source` field (`"ntes_live"` vs the default
  `"synthetic"`) so downstream consumers can distinguish real from
  synthetic numbers instead of presenting them identically.

## Frontend (`frontend/src/`)

All four must-build pages (spec section 8) are live, wired to real
`/api/plans/WEEKLY` output via a shared `PlanContext`: Overview, Weekly
plan (`WeeklyPlan.tsx` — day × section grid of blocks with capacity used,
unscheduled work with reasons, per-rule safety checks), Task queue, and
the Task/block detail panel. Beyond those:

- `WhatIf.tsx` — spec step 8. Queues disruptions (block cancelled, block
  granted late, new urgent defect), posts them to
  `/api/plans/WEEKLY/what-if`, and shows the before/after diff with the
  measured replan time and the replanned sections' safety checks.
- A time–distance (string) chart of blocks against paired NTES train
  movements was built and then removed on 2026-09-25 as unnecessary, along
  with the adapter's `/train-paths` endpoint that fed it. Recoverable from
  commits `36b18f1` (adapter) and `40cb357` (page, `TimeDistance.tsx`).
- `ReportDefect.tsx` (`/report`, field staff) — report a defect; it joins
  the backlog at once and the page says where the replanned week put it.
  The defect is typed in as free text and severity is a 1-10 score whose
  A/B/C band the backend works out (`operations.severity_from_score`); the
  form mirrors the bands only to show them while scoring.
- `RescheduleForm.tsx` — shared by both places a block can be moved. As
  the day, start and length change it checks the booked passenger
  timetable (`/api/corridors/{section}/timetable-check`, backend
  `app/timetable.py` over the adapter's "Trains between stations" data)
  and warns about trains booked over the block's km range then; "Suggest
  quiet times" lists the least-busy starts that day (`/quiet-slots`). A
  warning, never a veto. Passenger trains only, positions estimated —
  the form says so.
- `ControlOffice.tsx` (`/control`, control office) — one section and one
  night (noon to noon) at a time; grant, grant late, reschedule (new day,
  start and length within the plan week) or cancel each planned block,
  with the resulting task moves listed after each decision.
- `ChooseView.tsx` (`/`) — the first page: choose a view (control office,
  which has every planning page, or field staff), which picks the pages
  `App.tsx` puts in the nav;
  "change" in the nav returns here. Overview moved to `/overview`. Not
  access control; no login.
- `PrintPlan.tsx` (`/print?section=…`) — print-first weekly programme for
  the browser's Save as PDF, one section per printout, carrying that
  section's own fingerprint (`SectionPlanResult.fingerprint`). The page
  title includes the section so each saves as its own file. Marked as
  prototype output. Deliberately not styled as an official circular.

`RealDataBadge.tsx` surfaces each block's `data_source` (full badge in
the detail panel, a count KPI on Overview) so the real-vs-synthetic
distinction from `ntes_bridge.py` is visible, not just internal.
`CorridorMap.tsx` on Overview shows where blocks land along the corridor
by km; clicking a block there opens `BlockActionsPanel.tsx` to reschedule
or delete it (saved as the same control decisions Block Decisions makes,
through the shared `hooks/useBlockDecisions.ts`); `CorridorTraffic.tsx` shows real captured NTES train boards.

## Explicitly out of scope for this build

Real TMS/SMMS/TDMS/COA/BDMS connections, a trained ML model, network-scale
solving, auth/roles, approval workflow, monthly horizon. See spec section 1.

## Notes

- OR-Tools CP-SAT is the scheduler engine. Every solve goes through
  `scheduling/common.py:new_solver()` (one worker, fixed seed), because
  the default parallel search returned different equally-optimal plans
  for the same input — measured on GHY-LMG and NDLS-GZB — which made the
  plan change on refresh.
- The old TMS/SMMS/TDMS/COA adapter layer from the earlier skeleton was
  removed; it doesn't match this spec's data flow (synthetic-only, no
  external connections for this build).
