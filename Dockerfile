# Railmaster in one container, for a hosted demo (see render.yaml):
#   - the dashboard, built here and served by the backend on $PORT
#   - the backend (FastAPI + CP-SAT)
#   - ntes-adapter on 127.0.0.1:8001, replaying the captured NTES pages
#     (fixture mode) -- a hosted demo never scrapes NTES itself.

FROM node:20-slim AS dashboard
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Blocks, timetables and "tonight" are Indian railway local time; the
    # host's clock is UTC.
    TZ=Asia/Kolkata
WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
COPY ntes-adapter/requirements.txt ntes-adapter/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r ntes-adapter/requirements.txt

COPY backend/app backend/app
COPY ntes-adapter/app ntes-adapter/app
# The fixture provider replays these captured NTES responses.
COPY ntes-adapter/tests/fixtures ntes-adapter/tests/fixtures
COPY deploy/start.sh deploy/start.sh
COPY --from=dashboard /build/dist frontend/dist

ENV RAILMASTER_FRONTEND_DIST=/srv/frontend/dist \
    NTES_ADAPTER_PROVIDER=fixture \
    NTES_ADAPTER_BASE_URL=http://127.0.0.1:8001
EXPOSE 8000
CMD ["sh", "deploy/start.sh"]
