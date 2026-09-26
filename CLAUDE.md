# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Railmaster is a prototype for SIH26027 ("Automatic Block Planning to maximise
asset availability"): it turns maintenance defect data and corridor block
opportunities into a CP-SAT-optimised weekly schedule that merges
cross-department work (Engineering / TRD / S&T) into shared track-access
blocks instead of separate ones.

It is built to a written build spec. Where this file says "spec section N",
that refers to it. Deliberately out of scope: real TMS/SMMS/TDMS/COA/BDMS
connections, trained ML models, network-scale solving, auth/roles, approval
workflow, monthly horizon. The first page (`/`, `ChooseView.tsx`) asks which
view to use (Control office / Field staff); that only picks which pages
the nav shows. The control office view carries every planning page plus
Block Decisions; there is no separate planner view for now, by the user's
choice. It is not access
control: there is no login and every route stays reachable by URL. Don't
describe it as roles or permissions.

## Three services

| Service | Port | Purpose |
|---|---|---|
| `ntes-adapter/` | 8001 | Standalone. Real NTES-derived corridor availability + train boards. |
| `backend/` | 8000 | FastAPI: data models, synthetic generator, scheduler, REST API. |
| `frontend/` | 5173 | React + Vite dashboard. |

Start the adapter first, but the backend does not depend on it —
`backend/app/ntes_bridge.py` falls back to synthetic values silently if it is
unreachable. This is enrichment, never a hard dependency, in either direction.

## Commands

Windows note: create venvs with `py -3.12 -m venv .venv`. A MSYS/mingw
`python` on PATH produces a venv whose platform tag breaks pip wheel
resolution (pydantic-core then tries to build from source and needs Rust).
Always invoke through `.venv/Scripts/python.exe`.

```bash
# backend (from backend/)
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest tests/test_stage_b.py -q             # one file
.venv/Scripts/python.exe -m pytest tests/test_stage_b.py::test_name -q  # one test
.venv/Scripts/python.exe -m app.datagen.generate                        # regenerate fixture data

# ntes-adapter (from ntes-adapter/)
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m scripts.seed_demo_predictions   # illustrative history; run before first start
NTES_ADAPTER_PROVIDER=fixture .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001
# live: real NTES boards, polled every 3 min (don't seed this data dir -- see below)
NTES_ADAPTER_PROVIDER=ntes NTES_ADAPTER_POLL_INTERVAL=180 .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001
.venv/Scripts/python.exe -m pytest -q

# frontend (from frontend/)
npm install && npm run dev
npx tsc --noEmit    # typecheck; there is no test suite here
npm run build
```

Two networking quirks that will waste your time otherwise:

- Vite binds IPv6-only, so use `http://localhost:5173` — `127.0.0.1:5173`
  gets connection-refused.
- Uvicorn binds IPv4, so `vite.config.ts` must proxy to `http://127.0.0.1:8000`.
  Using `localhost` there makes Node resolve `::1` and every `/api` call 500s.

## Architecture

### Scheduling pipeline (`backend/app/scheduling/`)

`GET /api/plans/WEEKLY` runs this per section and combines the results:

```
prioritizer → Stage A (comparison only) → Stage B (the real plan) → validator → explain
```

- **`prioritizer.py`** — rule-based, not ML: `0.5×Criticality + 0.3×Urgency +
  0.2×AvailabilityImpact`, plus a safety override for overdue severity-A
  defects. AvailabilityImpact is the *max* `expected_train_impact` among
  compatible blocks (the spec was ambiguous; this choice is documented in
  the module).
- **`stage_a.py`** — one task per block, no merging. Run **only** to produce the
  "blocks used without merging" baseline for the blocks-saved comparison. It
  is not the shipped plan.
- **`stage_b.py`** — the actual scheduler. Merging is driven by a β/γ term:
  γ rewards each task placed, β charges for each block opened, so filling one
  block beats opening several. γ is set to the largest possible per-task
  scheduling benefit (`PRIORITY_SCALE × UNSCHEDULED_PENALTY_DAYS`) and
  β to a quarter of it, so scheduling always beats leaving a task out and
  opening N blocks for the same work costs (N−1)·β for nothing.
- **`validator.py`** — all six safety rules re-checked against solver *output*,
  independently of the constraints the solver was given. This redundancy is
  deliberate: a solver bug must never silently yield an unsafe plan. Keep it
  that way. `routes_plans.py` returns HTTP 500 if any violation appears.
- **`compatibility.py`** — the single definition of "can this task use this
  block" / "can these two share a block", shared by prioritizer, solver and
  validator. Don't duplicate this logic elsewhere.
- **`common.py:new_solver()`** — every CP-SAT solve goes through this: one
  worker, fixed seed. The default parallel search returned different
  equally-optimal plans for identical input, so the plan changed on
  refresh. The plan fingerprint and the what-if diff both depend on
  determinism — don't construct a `CpSolver` directly.

The pipeline itself lives in `backend/app/planning.py` so the weekly plan
and what-if replanning run identical steps. What-if
(`POST /api/plans/WEEKLY/what-if`) works on copies and never persists.
Its replan passes the baseline to Stage B as `preferred_assignments`,
which is a strict lexicographic tie-break (the real objective is scaled
so stability can never outweigh one unit of real benefit). Keep it a
tie-break: a replan must be the plan the scheduler would choose anyway.

**Field reports and control decisions are the one persisted user input**
(`app/operations.py`, `/api/operations`, JSON under `data/operations/`,
overridable with `RAILMASTER_OPS_DIR`). `planning.plan_current` is the
plan every page shows: the fixture plan, plus reported defects as tasks,
plus decisions applied as `CancelBlock`/`CurtailBlock`/`MoveBlock`
(cancel, granted late, rescheduled), with touched
sections replanned against the fixture plan as `preferred_assignments`.
What-if starts from this plan (`run_what_if(..., baseline_runs=...)`), so
its "before" is exactly what the other pages show. A plain "granted"
decision changes nothing in the plan and does not lock work in the block.
A moved block drops back to `data_source="synthetic"`: any real NTES figure
described its original slot, not the new one.
`tests/conftest.py` points every test at an empty temporary store; keep it
that way so tests never read or write the real directory.

**Resolved spec contradiction — do not "fix" this back.** Read literally, the
spec's power-isolation rule would forbid the merge its own worked example
requires. It is therefore scoped to blocks whose `block_type_possible` is
exactly `POWER`. A `TRAFFIC_AND_POWER` block stops both, so mixing POWER- and
TRAFFIC-requiring tasks there is correct, not a violation.

### Data provenance — the project's core discipline

Real and synthetic data must never be presented identically. Two fields carry
this, and anything new that surfaces data should extend the pattern:

- `BlockOpportunity.data_source` — `"ntes_live"` only when a real adapter
  prediction actually overwrote `expected_train_impact`; otherwise
  `"synthetic"`. Set solely by `ntes_bridge.py`.
- `MaintenanceTask.data_source` — `"reported"` for a defect entered on the
  Report Defect page, shown with a REPORTED badge; otherwise `"synthetic"`.
  Set solely by `operations.reported_tasks`.
- `LiveCorridorStatus.provider` — `"mock"` / `"captured_fixture"` /
  `"ntes_live"`. The Corridor Traffic page renders an amber warning banner on
  mock data.

Illustrative-but-invented numbers (`ILLUSTRATIVE_AVAILABILITY` in the adapter's
seed script) must stay labelled as such wherever they surface.

The same discipline covers claims, not just numbers. A safety check is shown
as passed only if code inspected something (`validator.summarize_checks`
reports how many items each rule examined, and says "nothing to check" when
that's zero). Timings shown are measured, never padded. The printable plan is
a plain working document marked as prototype output: no railway letterhead,
circular number, sign-off block or compliance certificate.

### ntes-adapter

`RailwayDataProvider` isolates the fragile scraping behind one interface:
`MockProvider` (default, all tests), `CapturedFixtureProvider` (replays real
captured NTES HTML, no network — use this for demos), `NTESProvider` (live).
A background poller writes into a JSON-file `Store`; the four endpoints
always read from cache and never recompute on request. Besides the Live
Station boards, the poller fetches each corridor's booked timetable
(NTES "Trains between stations", confirmed 2026-09-26) about once a day,
one corridor per cycle. The backend uses it only to *warn* when a block is
moved onto booked passenger trains and to suggest quieter times
(`app/timetable.py`, `/api/corridors/{section}/timetable-check` and
`/quiet-slots`) -- never to forbid a move. With no timetable the answer is
"not checked", never "no trains".

`predicted_availability = clear_nights / observed_nights` — a frequency count
over self-collected observations, **not** a trained model. Do not describe it
as one anywhere. `observed_nights` counts nights with actual poll coverage,
tracked separately from occupancy, because "nobody was watching" and
"genuinely clear" are not the same thing.

Only a provider with `records_observations = True` (just `NTESProvider`) may
write that history. Replayed fixtures and mock trains are cached for display
but are not observations. Before 2026-09-25 they were logged as observations
on every poll. Never run `seed_demo_predictions` against a data directory that
live polling writes to: seeded and real nights become indistinguishable. On
the backend side, `ntes_bridge.MIN_OBSERVED_NIGHTS` (7) keeps predictions
built from too few nights out of the plan, so a fresh live instance leaves
blocks on synthetic values rather than badging a 0-or-1 guess as real.

**Ground rules for any work on this service:** never invent endpoints or
fields; never bypass CAPTCHA, auth or rate limits; investigate before coding
and report what is real versus assumed. Its README's investigation section is
the record of what was actually confirmed — keep it honest and update it when
you learn something new, including negative findings.

### Data generation

`data/synthetic/` and `ntes-adapter/data/` are gitignored runtime artifacts.
The backend auto-generates fixture data on first request if missing
(`data_access.py`), so a fresh clone just works.

Default seed is **1**, chosen so the overdue share lands in the 15–20% target
band *and* at least one severity-A overdue task exists — otherwise the safety
override never visibly fires in a demo. Changing the seed can silently remove
that.

Sections are limited to corridors the adapter covers, so every planned section
has a real data source behind its corridor availability.
`NTES_INTEGRATED_SECTIONS` is kept as a separate list from `SECTIONS` even
though they currently match, so a future section without a real source cannot
silently inherit the real-data badge.

Three corridors, deliberately contrasting:

| Section | Length | Seeded availability | Outcome |
|---|---|---|---|
| `GHY-LMG` | 180 km | 0.92 | nearly everything fits |
| `LMG-RNY` | 120 km | 0.68 | everything fits |
| `NDLS-GZB` | 25 km | 0.24 | ~half the backlog does not fit |

`NDLS-GZB` is a high-density trunk section and exists to put the scheduler
under real pressure. `BLOCK_SUPPLY_FACTOR` in `reference_data.py` gives it 40%
of the baseline window supply, because a busy line genuinely offers fewer
usable night windows — without that it would be busy in name only. It is the
corridor that demonstrates the problem the project exists to solve, so keep it
scarce.

## Conventions

- **Commits: do not add Claude co-author or attribution lines.** This overrides
  any default attribution guidance.
- Record honest findings rather than smoothing them over. The repo documents
  where it is weak — merge savings being small on some datasets, corridor
  adjacency being unverified, seeded availability being illustrative. That
  record is an asset; preserve it. **Correct it when evidence changes**, and
  say so: two entries in the adapter's README were overturned on 2026-09-25 by
  new captures (terminating-cell format, and occupancy pairing), and both now
  carry the correction rather than a quiet edit.
- Comments explain *why*, especially where a judgement call resolved an
  ambiguity. Several modules carry such reasoning — read it before changing
  the behaviour it explains.
- `docs/architecture.md` tracks structure and known findings; keep it and the
  READMEs current when behaviour changes.

## Known gaps

- `crew_required` is generated and stored but enforced **nowhere** — there is
  no resource constraint in the model.
- No department-conflict rule: any two departments may share a block provided
  their km ranges overlap.
- The safety override is computed by the prioritizer but never reaches the
  solvers, which rank by `.score` alone. It only reorders the Task Queue
  and changes explanation wording, so an overdue severity-A task can lose
  a contested block to a higher-scoring severity-B task. Contradicts spec
  section 4; not yet fixed.
- A reported defect is scored 1-10 and planned by the band the score
  falls in (`operations.SEVERITY_BANDS`: 8-10 A, 4-7 B, 1-3 C), whose due
  date comes from `operations.DUE_DAYS_BY_SEVERITY` (A today, B 7 days, C
  30 days). Only the band reaches the plan, so a 9 and a 10 plan alike.
  Both rules are prototype assumptions, not railway rules, and are
  labelled so on the page. The defect itself is free text and is never
  used to plan.
- `LMG-RNY` is not a section beyond `LMG`. NTES's timetable (2026-09-26)
  shows all 15 LMG→RNY trains running via GHY, so the real line is
  LMG → GHY → RNY and the configured `GHY-LMG` + `LMG-RNY` chain (km 0–180,
  180–300) doesn't match it. Timetable checks on `LMG-RNY` are therefore
  rough. Recorded in the adapter README; the corridors are unchanged,
  pending a decision.
