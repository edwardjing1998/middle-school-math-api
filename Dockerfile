FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8282

WORKDIR /app

COPY requirements.txt ./

RUN python -m pip install \
    --no-cache-dir \
    --upgrade \
    pip \
    setuptools \
    wheel \
    && python -m pip install \
    --no-cache-dir \
    -r requirements.txt

COPY . ./

RUN chgrp -R 0 /app \
    && chmod -R g=u /app

EXPOSE 8282

CMD ["gunicorn", "--bind", "0.0.0.0:8282", "--workers", "2", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "main:app"]