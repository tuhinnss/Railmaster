#!/bin/sh
# Starts the container's two processes (see ../Dockerfile). The adapter runs
# in the background; if it fails the backend carries on with synthetic
# values, as it does locally. The backend runs in the foreground, so the
# container lives and dies with it.
set -e

(cd /srv/ntes-adapter && python -m uvicorn app.main:app --host 127.0.0.1 --port 8001) &

cd /srv/backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
