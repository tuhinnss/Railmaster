"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.config import APP_NAME, API_PREFIX
from app.api import routes_health, routes_defects, routes_corridors, routes_operations, routes_plans

app = FastAPI(title=APP_NAME)

app.include_router(routes_health.router, prefix=API_PREFIX)
app.include_router(routes_defects.router, prefix=API_PREFIX)
app.include_router(routes_corridors.router, prefix=API_PREFIX)
app.include_router(routes_plans.router, prefix=API_PREFIX)
app.include_router(routes_operations.router, prefix=API_PREFIX)

# In a deployment (see Dockerfile) the backend also serves the built
# dashboard, so the pages and /api share one origin -- what Vite's dev proxy
# does locally. Only when RAILMASTER_FRONTEND_DIST is set: in development
# the dashboard comes from Vite and a stale frontend/dist must not answer.
_dist = os.environ.get("RAILMASTER_FRONTEND_DIST")
if _dist:
    FRONTEND_DIST = Path(_dist).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def dashboard(path: str):
        # Registered last, so every /api route wins; an unknown /api path is
        # a 404, not the dashboard.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(FRONTEND_DIST):
            return FileResponse(file)
        # A missing build file must not come back as the page: a browser
        # holding an old index.html would try to run HTML as a script.
        if path.startswith("assets/"):
            raise HTTPException(status_code=404)
        # Any other path is a dashboard route (/overview, /control, ...):
        # the single-page app handles it.
        return FileResponse(FRONTEND_DIST / "index.html")
