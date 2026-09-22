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
- `scheduling/` — `compatibility.py` (shared task/block compatibility check,
  spec section 6), `config.py` (tunable `PriorityWeights`), `prioritizer.py`
  (rule-based score, section 4), `validator.py` (all 6 safety rules, run
  against solver output, section 6), `stage_a.py` (single-section CP-SAT,
  no merging, section 5 — done, ~20ms/section on the demo dataset). TODO:
  Stage B (merging, section 5), explainability (section 7).
- `api/` — FastAPI routers exposing tasks, blocks, and generated plans to
  the dashboard.

## Frontend (`frontend/src/`)

Four must-build pages (spec section 8): Overview, Task queue, Weekly plan
(Gantt), Task/block detail panel. Build these end to end against real
scheduler output before touching the what-if view or the differentiator
view.

## Explicitly out of scope for this build

Real TMS/SMMS/TDMS/COA/BDMS connections, a trained ML model, network-scale
solving, auth/roles, approval workflow, monthly horizon. See spec section 1.

## Notes

- OR-Tools CP-SAT is the scheduler engine (not yet added to
  `requirements.txt` — add when Stage A starts).
- The old TMS/SMMS/TDMS/COA adapter layer from the earlier skeleton was
  removed; it doesn't match this spec's data flow (synthetic-only, no
  external connections for this build).
