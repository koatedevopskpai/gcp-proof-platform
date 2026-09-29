FROM python:3.12-slim

WORKDIR /app

COPY services/evaluator/requirements.txt ./eval-requirements.txt
COPY mlops/bigquery/requirements.txt ./bq-requirements.txt
RUN pip install --no-cache-dir -r eval-requirements.txt -r bq-requirements.txt

COPY services/evaluator/evaluator /app/evaluator
COPY services/evaluator/datasets /app/datasets
COPY mlops/bigquery/run_pipeline.py /app/run_pipeline.py

ENV PYTHONPATH=/app
ENTRYPOINT ["python", "/app/run_pipeline.py"]