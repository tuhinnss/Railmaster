# Railmaster

Automatic Block Planning prototype for Indian Railways fixed infrastructure
maintenance (Engineering / TRD / S&T). Turns synthetic-but-realistic
defect/maintenance data and corridor block opportunities into a
CP-SAT-optimized weekly block schedule that merges cross-department work
into shared blocks instead of separate ones, with a real (if partial)
data connection: two of the six configured sections pull real
predicted-availability data from a separate NTES-derived service instead
of pure synthetic numbers.

Scope is deliberately narrow for this build — see `docs/architecture.md`
and the build spec for what's in/out.

## Structure

- `backend/` — FastAPI service: typed data models (`app/models`), synthetic
  data generator (`app/datagen`), scheduling engine (`app/scheduling`),
  the NTES enrichment bridge (`app/ntes_bridge.py`), REST API (`app/api`).
- `frontend/` — React dashboard: Overview, Task queue, Weekly plan (Gantt),
  Task/block detail panel, Corridor traffic (real NTES train boards) —
  wired to real scheduler output.
- `ntes-adapter/` — separate service; see its own README. Provides real,
  self-collected train-movement-derived predicted-availability data for
  two corridors (GHY-LMG, LMG-RNY).
- `docs/` — architecture notes.
- `data/synthetic/` — generated fixture data (gitignored, reproducible via
  `python -m app.datagen.generate` from `backend/`).

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
safety validator, explainability) and the dashboard (all 4 required
pages) are done and wired end to end — 56 backend tests passing. The
NTES connection covers 2 of 6 sections; the rest remain synthetic, and
every block carries a `data_source` field (`"ntes_live"` vs
`"synthetic"`) so the dashboard can show a "REAL NTES DATA" badge on the
Weekly Plan Gantt, the task/block detail panel, and an Overview KPI
count, instead of presenting real and synthetic numbers identically.
Not yet built: the what-if scenario view (spec step 8), explicitly
lower priority than a working core.
