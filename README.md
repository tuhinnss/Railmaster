# Railmaster

Automatic Block Planning prototype for Indian Railways fixed infrastructure
maintenance (Engineering / TRD / S&T). Turns synthetic-but-realistic
defect/maintenance data and corridor block opportunities into a
CP-SAT-optimized weekly block schedule that merges cross-department work
into shared blocks instead of separate ones.

Scope is deliberately narrow for this build — see `docs/architecture.md`
and the build spec for what's in/out.

## Structure

- `backend/` — FastAPI service: typed data models (`app/models`), synthetic
  data generator (`app/datagen`), scheduling engine (`app/scheduling`, WIP),
  REST API (`app/api`).
- `frontend/` — React dashboard: Overview, Task queue, Weekly plan (Gantt),
  Task/block detail panel.
- `docs/` — architecture notes.
- `data/synthetic/` — generated fixture data (gitignored, reproducible via
  `python -m app.datagen.generate` from `backend/`).

## Backend setup

```
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m app.datagen.generate   # writes data/synthetic/{tasks,blocks}.json
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

## Frontend setup

```
cd frontend
npm install
npm run dev
```

## Status

Models + synthetic data generator done. Scheduler (priority score, CP-SAT
Stage A/B, safety validator, explainability) and dashboard are next.
