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
  `--seed` (default 4, lands in the 15-20% overdue target band).
  Run: `python -m app.datagen.generate` from `backend/`.
- `scheduling/` — `common.py` (shared constants/delay calc), `compatibility.py`
  (task/block + task/task compatibility, section 6), `config.py` (tunable
  `PriorityWeights`), `prioritizer.py` (rule-based score, section 4),
  `validator.py` (all 6 safety rules, run against solver output, section 6),
  `stage_a.py` (single-section CP-SAT, no merging, section 5), `stage_b.py`
  (merging via beta/gamma consolidation incentive, section 5 — done, worked
  example passes, ~40ms/section), `explain.py` (one-line generated reason
  per task, section 7 — done).

  Known finding: on the random synthetic dataset, Stage B only saves ~5%
  of blocks vs. Stage A (2 of 43), because task durations often consume
  most of a block's capacity and km ranges are narrow, so few combinations
  are actually mergeable outside the deliberate overlap fixture. The
  worked example and a dedicated preference test both confirm the merge
  logic itself is correct. Getting a bigger "blocks saved" headline number
  is a data-tuning / demo-scenario-curation task for spec step 10, not an
  algorithm fix.
- `api/` — FastAPI routers exposing tasks, blocks, and generated plans to
  the dashboard.
- `ntes_bridge.py` — optional enrichment layer connecting to the separate
  `ntes-adapter/` service (real NTES-derived predicted-availability data,
  see its own README). For the two NTES-integrated sections
  (`GHY-LMG`, `LMG-RNY`, per `datagen/reference_data.NTES_INTEGRATED_SECTIONS`),
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

Four must-build pages (spec section 8): Overview, Task queue, Weekly plan
(Gantt), Task/block detail panel — done, wired to real `/api/plans/WEEKLY`
output via a shared `PlanContext`. `RealDataBadge.tsx` surfaces each
block's `data_source` (dot marker on Gantt bars, full badge in the detail
panel, a count KPI on Overview) so the real-vs-synthetic distinction from
`ntes_bridge.py` is visible, not just internal.

## Explicitly out of scope for this build

Real TMS/SMMS/TDMS/COA/BDMS connections, a trained ML model, network-scale
solving, auth/roles, approval workflow, monthly horizon. See spec section 1.

## Notes

- OR-Tools CP-SAT is the scheduler engine (not yet added to
  `requirements.txt` — add when Stage A starts).
- The old TMS/SMMS/TDMS/COA adapter layer from the earlier skeleton was
  removed; it doesn't match this spec's data flow (synthetic-only, no
  external connections for this build).
