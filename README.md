# Railmaster

Automatic Block Planning prototype for Indian Railways fixed infrastructure
maintenance (Engineering / TRD / S&T). Turns synthetic-but-realistic
defect/maintenance data and corridor block opportunities into a
CP-SAT-optimized weekly block schedule that merges cross-department work
into shared blocks instead of separate ones.

Scope is limited to corridors the NTES adapter actually covers, so every
planned section has a real data source behind its corridor availability
rather than being wholly invented. The defect/maintenance data itself is
still synthetic.

Three corridors, chosen to contrast: the quiet Assam pair (GHY-LMG,
LMG-RNY) where nearly all maintenance fits, and the high-density
Delhi–Ghaziabad trunk section (NDLS-GZB) where roughly half the backlog
cannot be accommodated — the situation the system exists to address.
Selectable on the Overview.

Scope is deliberately narrow for this build — see `docs/architecture.md`
and the build spec for what's in/out.

## Structure

- `backend/` — FastAPI service: typed data models (`app/models`), synthetic
  data generator (`app/datagen`), scheduling engine (`app/scheduling`),
  the NTES enrichment bridge (`app/ntes_bridge.py`), REST API (`app/api`).
- `frontend/` — React dashboard, all wired to real scheduler output:
  Overview (KPIs + corridor map), Weekly plan (day × section grid, with a
  per-section printable version), Task queue + detail panel, What-if
  replanning, Corridor traffic (real NTES train boards), Report Defect
  (field staff) and Block Decisions (control office). The first page
  (`/`) asks who you are — control office or field staff — and each
  view gets its own nav. The control office sees the whole block
  allocation (every planning page plus Block Decisions); there is no
  separate planner view for now. The Overview lives at `/overview`.
- `ntes-adapter/` — separate service; see its own README. Provides real,
  self-collected train-movement-derived predicted-availability data, plus
  real captured NTES train boards, for the three corridors.
- `docs/` — architecture notes.
- `data/synthetic/` — generated fixture data (gitignored, reproducible via
  `python -m app.datagen.generate` from `backend/`).
- `data/operations/` — defects reported and block decisions recorded on the
  dashboards (gitignored; delete it to start clean).

## Running the full stack

```bash
# 1. ntes-adapter (optional but recommended -- without it, GHY-LMG and
#    LMG-RNY just use synthetic data like every other section)
cd ntes-adapter
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m scripts.seed_demo_predictions   # illustrative history, see its README
# NTES_ADAPTER_PROVIDER=fixture serves the real captured NTES train boards
# (Corridor Traffic page). Omit it for canned mock trains.
NTES_ADAPTER_PROVIDER=fixture .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001
# Or live: polls NTES's unofficial Live Station page every 3 minutes and
# builds real availability history night by night. Skip the seeding step
# above for a live data directory -- see ntes-adapter/README.md.
# NTES_ADAPTER_PROVIDER=ntes NTES_ADAPTER_POLL_INTERVAL=180 .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001

# 2. backend
cd backend
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 3. frontend
cd frontend
npm install && npm run dev
# open http://localhost:5173 (not 127.0.0.1 -- Vite may bind IPv6-only)
```

Data auto-generates on first request if `data/synthetic/` doesn't exist.
The backend works fine with ntes-adapter not running — `ntes_bridge.py`
falls back to synthetic values silently if it's unreachable.

## Status

Backend engine (schema, synthetic data, priority score, CP-SAT Stage A/B,
safety validator, explainability, what-if replanning) is done and wired
end to end — 125 backend + 62 adapter tests passing. Dashboard ships
Overview, Weekly plan (+ per-section printable version), Task queue,
detail panel, What-if, Corridor traffic, Report Defect and Block
Decisions.

The solver is deterministic (one CP-SAT worker, fixed seed). The default
parallel search returned different, equally optimal plans for the same
input on two of the three sections, so the plan could change on a plain
refresh. Each plan now carries a SHA-256 fingerprint of what it commits
to, which is only meaningful because of that — see
`backend/app/scheduling/common.py`.

What-if (`POST /api/plans/WEEKLY/what-if`) applies block cancellations,
late-granted blocks and injected urgent defects to an in-memory copy of
the data, re-runs the full pipeline on the affected sections, and diffs
the result. Among equally good replans it keeps the current plan (a
strict tie-break in Stage B), so every listed change is one the
disruption forced. Nothing is persisted.

Report Defect and Block Decisions are the persisted counterpart
(`/api/operations`, `backend/app/operations.py`). A reported defect joins
its section's backlog as a task marked `REPORTED`; a control office can
mark a planned block granted, granted late (the block shortens),
rescheduled to another day and time in the plan week (optionally with a
new length), or cancelled (it leaves the plan). Under the Overview's block
map, "Work that didn't fit" lists what the plan couldn't place, with the
planner's reason; **Schedule…** adds a block for it at a chosen time
(checked against the booked timetable like a move). The block is held for
that work, other work may share it alongside, and it is marked ADDED
everywhere: no corridor data offered it, so it has no train-impact figure.
Every page then shows the fixture plan
with these applied, replanned with the same keep-the-current-plan
tie-break, so only work that has to move does. What-if scenarios start
from this plan. The view chosen on the first page only changes which pages
the nav shows: there is no login, and every page stays reachable by URL.

Every block carries a `data_source` field (`"ntes_live"` vs
`"synthetic"`, or `"added"` for a block added by hand), surfaced as a badge in the detail panel and an Overview
KPI, so real and synthetic numbers are never presented identically. A
block only counts as real when it falls in a window the adapter has
observations for.

Known gaps, in rough priority order:

- The safety override (overdue severity-A outranks every non-A task, spec
  section 4) is computed but only reorders the Task queue and the
  explanation text. Both solvers rank by the weighted score alone, so an
  overdue severity-A task can lose a contested block to a long-overdue
  severity-B task with a higher score.
- `crew_required` is generated and stored but enforced nowhere — no
  resource constraint exists.
- No department-conflict rule: any two departments may share a block
  provided their km ranges overlap.
- Granting a block records the go-ahead but does not lock the work inside
  it: a later report or cancellation can still move that work elsewhere.
- Moving a block is checked against the booked *passenger* timetable
  only (NTES "Trains between stations", fetched about daily by the
  adapter): it warns, suggests quieter times, and never blocks the move.
  Goods trains are in no public timetable; a train's position between the
  section ends is estimated at a steady speed; both directions count; and
  whether a train's running days count from this station or its origin is
  unconfirmed. Nothing checks a moved block against other blocks either —
  two blocks on a section can overlap in time.
- A reported defect's severity is a 1-10 score, planned by its band
  (8-10 is A, due today; 4-7 is B, due within 7 days; 1-3 is C, due
  within 30). Only the band counts, so a 9 and a 10 are planned alike.
  The bands and due dates are prototype assumptions, not a railway
  standard.
