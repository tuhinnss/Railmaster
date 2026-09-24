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
- `frontend/` — React dashboard: Overview (KPIs + corridor map), Task queue,
  Task/block detail panel, Corridor traffic (real NTES train boards) —
  wired to real scheduler output. The Weekly plan (Gantt) page was removed
  pending a rebuild; the backend still produces the full plan, and the
  removed page is recoverable from git history (see `de3be0c`).
- `ntes-adapter/` — separate service; see its own README. Provides real,
  self-collected train-movement-derived predicted-availability data, plus
  real captured NTES train boards, for the three corridors.
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
safety validator, explainability) is done and wired end to end — 57
backend + 41 adapter tests passing. Dashboard currently ships Overview,
Task queue, detail panel and Corridor traffic.

Every block carries a `data_source` field (`"ntes_live"` vs
`"synthetic"`), surfaced as a badge in the detail panel and an Overview
KPI, so real and synthetic numbers are never presented identically. A
block only counts as real when it falls in a window the adapter has
observations for.

Known gaps, in rough priority order:

- Weekly plan (Gantt) page removed pending a rebuild — the scheduler
  still produces the plan, it just isn't visualised on a timeline.
- `crew_required` is generated and stored but enforced nowhere — no
  resource constraint exists.
- No department-conflict rule: any two departments may share a block
  provided their km ranges overlap.
- What-if scenario view (spec step 8) not built.
