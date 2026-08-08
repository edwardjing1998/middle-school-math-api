FROM nvidia/cuda:13.2.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8282 \
    CHROMA_DB_PATH=/app/data/chroma

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/chroma \
    && chgrp -R 0 /app \
    && chmod -R g=u /app

EXPOSE 8282

CMD ["gunicorn", "--workers", "1", "--threads", "4", "--bind", "0.0.0.0:8282", "--timeout", "180", "--access-logfile", "-", "--error-logfile", "-", "main:app"]
