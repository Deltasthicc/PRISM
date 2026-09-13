# Backend runtime image. Only exists because of one dependency: OCR (see
# ai/ingestion.py's scanned-PDF/image fallback). pytesseract is just a thin
# Python wrapper -- it shells out to the real `tesseract` binary, which the
# pip package does NOT bundle and which Render's native "runtime: python"
# buildpack has no way to `apt-get install` onto. Docker is the only way to
# get that binary into the deployed environment, so render.yaml's
# prism-backend service now builds from this file instead of
# `pip install -r requirements.txt` directly (mirrors prism-keycloak's own
# runtime: docker + dockerfilePath pattern in render.yaml).
#
# python:3.11-slim (Debian-based) matches backend/.python-version (3.11.9)
# and the Python version this repo's CI (.github/workflows/ci.yml) already
# runs the full test suite against.
FROM python:3.11-slim

# tesseract-ocr pulls in its own English language data by default
# (tesseract-ocr-eng) as a dependency of the tesseract-ocr package on
# Debian -- no separate language-pack install needed for the English-only
# scope this ingestion pipeline currently targets.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first so Docker's layer cache skips the (slow) dependency
# install on rebuilds that only change application code.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render sets $PORT at runtime; alembic upgrade head runs the same migration
# step render.yaml's previous native startCommand already ran, unchanged.
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"]
