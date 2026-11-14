# Pathway platform: the service (API, jobs) serving the built web app. One process, one volume at /data.
#
#   docker build -t pathway-platform .                 # needs web/ (branch plat/web, once merged)
#   docker build --target api -t pathway-api .         # the API alone, without the web app
#   docker run -p 8000:8000 -v pathway-data:/data \
#          -e PATHWAY_ACCESS_TOKEN="$(openssl rand -hex 24)" pathway-platform
#
# The image sets PATHWAY_REQUIRE_AUTH=1: it refuses to start without a token (or PATHWAY_PUBLIC_READ=1).
# Run exactly one container per volume and one uvicorn process: jobs are child processes of the service
# (service/runtime.py), and SQLite is not shared between hosts.

# ---- web app: only built for the default target ----
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- API ----
FROM python:3.13-slim AS api
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt /tmp/req-sim.txt
COPY service/requirements.txt /tmp/req-service.txt
RUN pip install -r /tmp/req-sim.txt -r /tmp/req-service.txt
# demo/export.py builds the result bundle the dashboard reads; the rest of demo/ is not needed
COPY demo/export.py demo/export.py
COPY jev jev
COPY pathway_sim pathway_sim
COPY optimiser optimiser
COPY decision_model decision_model
COPY params params
COPY scenarios scenarios
COPY service service
COPY deploy/backup.py deploy/seed.py deploy/
RUN useradd --system --uid 10001 --home-dir /app pathway && mkdir /data && chown pathway /data
ENV PATHWAY_DATA_DIR=/data PATHWAY_SCENARIO_DIR=/app/scenarios PATHWAY_WEB_DIR=/app/web/dist \
    PATHWAY_REQUIRE_AUTH=1 FORWARDED_ALLOW_IPS=127.0.0.1
VOLUME /data
USER pathway
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
# --proxy-headers trusts X-Forwarded-For only from FORWARDED_ALLOW_IPS; compose widens that for its loopback-only port.
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]

# ---- default target: API plus the built web app ----
FROM api AS final
COPY --from=web /web/dist /app/web/dist
