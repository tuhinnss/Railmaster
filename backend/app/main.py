"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload"""

from fastapi import FastAPI

from app.config import APP_NAME, API_PREFIX
from app.api import routes_health, routes_defects, routes_corridors, routes_operations, routes_plans

app = FastAPI(title=APP_NAME)

app.include_router(routes_health.router, prefix=API_PREFIX)
app.include_router(routes_defects.router, prefix=API_PREFIX)
app.include_router(routes_corridors.router, prefix=API_PREFIX)
app.include_router(routes_plans.router, prefix=API_PREFIX)
app.include_router(routes_operations.router, prefix=API_PREFIX)
