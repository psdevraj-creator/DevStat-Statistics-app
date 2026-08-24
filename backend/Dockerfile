# DevStat backend container (serves the built SPA + API + auth/billing).
# Build context must be the backend/ directory.
FROM python:3.12-slim

WORKDIR /app

# Install Python deps first (cached layer).
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App code, analysis engine (pure Python), and the built frontend SPA.
COPY app ./app
COPY r ./r
COPY static ./static

ENV PYTHONPATH=/app
EXPOSE 8080

# Cloud Run supplies the port via $PORT automatically for uvicorn? uvicorn needs it;
# we default to 8080 and cloudrun sets PORT (we read it below).
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]
