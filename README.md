# Railmaster

Automatic Block Planning system for Indian Railways fixed infrastructure
maintenance (Engineering / Traction Distribution / Signal & Telecom).

Integrates defect & maintenance data from TMS, SMMS, and TDMS with corridor
block availability from COA (train timetable + goods forecast), then uses
a prioritization + optimization engine to generate coordinated weekly and
monthly maintenance block schedules.

## Structure

- `backend/` — FastAPI service: data models, source-system adapters (mocked
  for now), prioritization/scheduling engine, REST API.
- `frontend/` — React dashboard for viewing and reviewing block plans.
- `docs/` — architecture notes.

## Status

Skeleton only — building out piece by piece.
