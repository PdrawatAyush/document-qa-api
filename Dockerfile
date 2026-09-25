FROM python:3.11-slim

WORKDIR /app

# build-essential: needed to build some Python wheels (e.g. tokenizers) on
#   slim images if a prebuilt wheel isn't available for this platform.
# libgomp1: the GNU OpenMP runtime -- torch (a sentence-transformers
#   dependency) is linked against it and importing torch fails at runtime
#   on python:3.11-slim with "libgomp.so.1: cannot open shared object file"
#   if it isn't explicitly installed (it is not guaranteed to be pulled in
#   as a transitive dependency of build-essential).
# curl: used for basic in-container debugging/health checks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
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
