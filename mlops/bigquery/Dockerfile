FROM python:3.12-slim

# Pull patched base packages so the Trivy HIGH/CRITICAL gate passes
# (perl-base CVEs fixed in debian bookworm updates).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/evaluator/requirements.txt ./eval-requirements.txt
COPY mlops/bigquery/requirements.txt ./bq-requirements.txt
RUN pip install --no-cache-dir -r eval-requirements.txt -r bq-requirements.txt

COPY services/evaluator/evaluator /app/evaluator
COPY services/evaluator/datasets /app/datasets
COPY mlops/bigquery/run_pipeline.py /app/run_pipeline.py

ENV PYTHONPATH=/app
ENTRYPOINT ["python", "/app/run_pipeline.py"]