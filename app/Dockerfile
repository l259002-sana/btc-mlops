# syntax=docker/dockerfile:1
# Build from the repo root:  docker build -f app/Dockerfile -t btc-forecast-api .

# ---------- Stage 1: build dependencies into a virtualenv ----------
FROM python:3.10-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Copy only requirements first so this layer is cached until dependencies change
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- Stage 2: slim runtime image ----------
FROM python:3.10-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    MODEL_DIR=/app/models \
    DATA_DIR=/app/data

# Non-root user
RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid 10001 --no-create-home appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/
COPY app/app.py app/entrypoint.sh ./
RUN mkdir -p /app/models /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:%s/health'%os.getenv('PORT','5000'))"
ENTRYPOINT ["./entrypoint.sh"]
