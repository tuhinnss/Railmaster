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

## How to run it

### What you need

- [Git](https://git-scm.com/)
- [Python](https://www.python.org/downloads/) 3.12 or newer (tested on 3.12
  and 3.13)
- [Node.js](https://nodejs.org/) 18 or newer, with npm (tested on 22)

### 1. Get the code

```bash
git clone https://github.com/tuhinnss/Railmaster.git
cd Railmaster
```

### 2. Start the three services

Open **three terminals**, each starting in the `Railmaster` folder, and
start the services in this order. Leave each one running. The commands
call the Python inside each service's own virtual environment directly,
so there is nothing to activate.

**Terminal 1: ntes-adapter** (port 8001), replaying the real NTES pages
captured during development:

```powershell
# Windows (PowerShell)
cd ntes-adapter
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:NTES_ADAPTER_PROVIDER = "fixture"
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001
```

```bash
# macOS / Linux
cd ntes-adapter
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
NTES_ADAPTER_PROVIDER=fixture .venv/bin/python -m uvicorn app.main:app --port 8001
```

**Terminal 2: backend** (port 8000):

```powershell
# Windows (PowerShell)
cd backend
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

```bash
# macOS / Linux
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8000
```

**Terminal 3: dashboard** (port 5173), the same on every system:

```bash
cd frontend
npm install
npm run dev
```

The `venv` and `install` lines are only needed the first time; after that,
start each service with its last line (plus the `$env:` line in
PowerShell, which lasts only for that terminal).

### 3. Open it

Go to **http://localhost:5173** (use `localhost`, not `127.0.0.1`: Vite may
listen on IPv6 only). The first page asks whether you are the control
office or field staff; that only picks which pages the menu shows.

The first page load takes a few seconds: the backend generates the
synthetic maintenance backlog and block opportunities for the coming week
(`data/synthetic/`) on its first request.

For the first few minutes after the adapter starts, the timetable check
used when moving a block may say "not checked": the adapter loads one
corridor's timetable per poll, about a minute apart (measured: NDLS-GZB
was ready 3–4 minutes after start).

### Options

- **Without the adapter.** The backend runs fine on its own: blocks keep
  synthetic availability, Corridor Traffic has no train boards, and the
  timetable check when moving a block says "not checked".
- **Adapter modes** (`NTES_ADAPTER_PROVIDER`):
  - `fixture` (used above): real captured NTES pages, replayed and
    labelled as such.
  - `mock` (the default when unset): invented trains. Corridor Traffic
    shows a warning banner.
  - `ntes`: polls NTES's live pages and builds real availability history
    night by night; blocks only use it once 7 nights have been observed.
    Always set `NTES_ADAPTER_POLL_INTERVAL=180` with it (every 3 minutes):
    the 60-second default is meant for the offline modes. Read
    `ntes-adapter/README.md` first.
- **Demo seeding: not needed, and read this before using it.**
  Running `.venv/bin/python -m scripts.seed_demo_predictions` (Windows:
  `.venv\Scripts\python.exe -m ...`) in `ntes-adapter`, before starting
  it, fills the adapter with made-up past nights so blocks use
  NTES-style availability straight away. Those blocks then show the
  **REAL NTES DATA** badge although the numbers are illustrative, not
  observed (see Known gaps). Never run it on a data folder that live
  polling writes to.

### Run the tests

```bash
# from backend/ and from ntes-adapter/ (use .venv\Scripts\python.exe on Windows)
.venv/bin/python -m pytest -q
# from frontend/: typecheck (there is no frontend test suite)
npx tsc --noEmit
```

### Start over

Stop the backend, delete `data/operations/` (saved reports, block
decisions and added blocks) and, to regenerate the week's synthetic data,
`data/synthetic/`. Then start the backend again.

### If something goes wrong

- **`127.0.0.1:5173` refuses to connect.** Use `http://localhost:5173`.
- **Every page says it failed to load the plan.** The backend isn't running
  on port 8000; the dashboard sends `/api` requests there
  (`frontend/vite.config.ts`).
- **Windows: `pip install` tries to build `pydantic-core` and asks for
  Rust.** The virtual environment was made with an MSYS/Git-Bash
  `python`. Delete `.venv` and recreate it with `py -m venv .venv`.
- **A port is already in use.** Stop whatever holds it. To move the
  adapter, start the backend with `NTES_ADAPTER_BASE_URL` pointing at the
  new port; to move the backend, change the proxy in
  `frontend/vite.config.ts`.
- **Docker instead.** With Docker installed, `docker build -t railmaster .`
  then `docker run -p 8000:8000 railmaster` runs all three in one
  container at http://localhost:8000 (see Hosted demo below).

## Hosted demo (Render)

`Dockerfile` builds the whole prototype into one container: the dashboard
is built and served by the backend (`RAILMASTER_FRONTEND_DIST`), so the
pages and `/api` share one origin, and ntes-adapter runs beside it in
fixture mode, replaying the captured NTES pages. A hosted copy never
scrapes NTES itself. `render.yaml` describes it as one free Render web
service: in Render, **New → Blueprint** and pick this repository; it
redeploys on every push to `main`.

What a free hosted copy is and isn't:

- It sleeps after ~15 idle minutes and takes about a minute to wake.
- Its disk isn't kept: reports, decisions and added blocks are cleared on
  every restart, wake-up or deploy, and the synthetic data is regenerated
  for the current week.
- NTES data is the 2026-09 captures, labelled as replayed. Blocks stay on
  synthetic availability (no observed nights), which the pages show.
- There is no login: anyone with the link can file reports and change
  blocks. It is a demo of prototype output, and the pages say so.
- It runs on Indian time (`TZ=Asia/Kolkata`), like the data.

To run the same image locally: `docker build -t railmaster .` then
`docker run -p 8000:8000 railmaster` and open http://localhost:8000.

## Status

Backend engine (schema, synthetic data, priority score, CP-SAT Stage A/B,
safety validator, explainability, what-if replanning) is done and wired
end to end — 127 backend + 62 adapter tests passing. Dashboard ships
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
- Demo seeding (`scripts.seed_demo_predictions`) makes blocks show the
  REAL NTES DATA badge although their availability comes from invented
  nights: the badge can't tell seeded history from observed history.
  Leave seeding out unless that demo is needed, and never seed a live
  data folder.
- A reported defect's severity is a 1-10 score, planned by its band
  (8-10 is A, due today; 4-7 is B, due within 7 days; 1-3 is C, due
  within 30). Only the band counts, so a 9 and a 10 are planned alike.
  The bands and due dates are prototype assumptions, not a railway
  standard.
