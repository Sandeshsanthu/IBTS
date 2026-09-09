FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install updated clean requirements directly
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY shared/ ./shared/

EXPOSE 8080

CMD ["opentelemetry-instrument", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
