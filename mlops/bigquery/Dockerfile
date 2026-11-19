FROM python:3.12-slim

# Pull patched base packages so the Trivy HIGH/CRITICAL gate passes
# (perl-base CVEs fixed in debian bookworm updates).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The image has no git, so stamp the commit at build time; reports record it in provenance.
ARG GIT_COMMIT=""
ENV GIT_COMMIT=$GIT_COMMIT

COPY services/evaluator/requirements.txt ./eval-requirements.txt
COPY services/evaluator/requirements-ragas.txt ./eval-ragas-requirements.txt
COPY mlops/bigquery/requirements.txt ./bq-requirements.txt
# RAGAS pulls langchain and pandas; this is why the job runs with 2 GiB and 1800s.
RUN pip install --no-cache-dir -r eval-requirements.txt -r eval-ragas-requirements.txt -r bq-requirements.txt

COPY services/evaluator/evaluator /app/evaluator
COPY services/evaluator/datasets /app/datasets
COPY mlops/bigquery/run_pipeline.py /app/run_pipeline.py

ENV PYTHONPATH=/app
ENTRYPOINT ["python", "/app/run_pipeline.py"]
