# Architecture (outline)

## Data flow

```
TMS  ──┐                                  ┌── Weekly plan
SMMS ──┼── integrations/ (adapters) ──┐    │
TDMS ──┘                              │    │
                                       ├──> scheduling/ ──┤
COA (corridor blocks +   ─────────────┘    (prioritize +   │
     timetable + goods                      optimize)      │
     forecast)                                              └── Monthly plan
```

## Backend layers (`backend/app/`)

- `models/` — core domain entities (Defect, MaintenanceTask, Corridor,
  BlockWindow, TrainTimetableEntry, BlockPlan).
- `integrations/` — one adapter per source system (TMS, SMMS, TDMS, COA)
  behind a common interface, so mock implementations can later be swapped
  for real system connectors without touching the scheduler.
- `mock_data/` — generators that produce realistic fake defects, tasks,
  corridor windows, and timetables for development/demo.
- `scheduling/`
  - `prioritizer.py` — scores maintenance tasks by criticality, urgency
    (overdue-ness), and asset-availability impact.
  - `optimizer.py` — assigns prioritized tasks to available corridor
    block windows, minimizing downtime and cross-department conflicts.
  - `horizon.py` — rolls the optimizer output into weekly/monthly plans.
- `api/` — FastAPI routers exposing defects, corridors, and generated plans.
- `schemas/` — request/response DTOs for the API.

## Frontend (`frontend/src/`)

- `pages/Dashboard.tsx` — overview (open defects, upcoming blocks).
- `pages/BlockPlans.tsx` — weekly/monthly plan view.
- `pages/Corridors.tsx` — corridor availability / block calendar.

## Open decisions (TBD as we build)

- Real vs. mocked persistence (likely start with in-memory / SQLite).
- Optimization approach: start greedy, evaluate OR-tools/constraint
  solver later if needed.
- Auth/multi-department access control — out of scope for skeleton.
