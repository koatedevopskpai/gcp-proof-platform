FROM python:3.12-slim

# Pull patched base packages so the Trivy HIGH/CRITICAL gate passes. The first CI run
# found zlib1g CVE-2026-85091 (fixed in a Debian point release) in this image.
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY datasets ./datasets
COPY scripts ./scripts

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]