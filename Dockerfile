FROM python:3.14-slim

LABEL privacy="Zero data retention. Data is processed in memory only."

# Install build tools AND runtime libraries for scipy/sklearn/numpy/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgfortran5 \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY sample_100.csv sample_medical_data.csv ./
COPY startup.sh .

RUN chmod +x startup.sh

WORKDIR /app/backend

ENV PORT=8080
ENV PYTHONPATH=/app/backend

CMD ["/app/startup.sh"]
