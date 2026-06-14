FROM python:3.14-slim

LABEL privacy="Zero data retention. Data is processed in memory only."

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY sample_100.csv sample_medical_data.csv ./

WORKDIR /app/backend

ENV PORT=8080
CMD uvicorn app.main:create_app --host 0.0.0.0 --port ${PORT} --factory
