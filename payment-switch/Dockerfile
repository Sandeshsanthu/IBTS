FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── 1. Install shared package (resolves transitive deps) ─────────────────────
COPY shared/ /tmp/shared/
RUN pip install --no-cache-dir /tmp/shared/

# ── 2. Install service dependencies ───────────────────────────────────────────
WORKDIR /app

COPY payment-switch/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 3. Copy service source ────────────────────────────────────────────────────
COPY payment-switch/app/         ./app/
COPY payment-switch/main.py      .
COPY payment-switch/init_resources.py .

# ── 4. Make shared importable as "shared.*" namespace ────────────────────────
COPY shared/ ./shared/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8083

CMD ["sh", "-c", "python init_resources.py && opentelemetry-instrument uvicorn main:app --host 0.0.0.0 --port 8083"]
