"""App settings. TODO: move to pydantic-settings / env vars as needs grow."""

import os

APP_NAME = "Railmaster"
API_PREFIX = "/api"

# ntes-adapter connection (see ../../ntes-adapter/). Separate service,
# separate process -- if it's unreachable, app/ntes_bridge.py falls back
# to the synthetic data untouched rather than failing the request.
NTES_ADAPTER_BASE_URL = os.environ.get("NTES_ADAPTER_BASE_URL", "http://127.0.0.1:8001")
