FROM python:3.11-slim

WORKDIR /app

# System deps needed to build some Python wheels (e.g. tokenizers) on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Where SQLite + Chroma data live inside the container; mounted as a volume
# in docker-compose so data survives container restarts.
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
