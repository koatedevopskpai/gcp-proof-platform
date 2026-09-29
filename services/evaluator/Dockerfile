FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY evaluator ./evaluator
COPY datasets ./datasets

# Cloud Build runs steps from /workspace, not the image WORKDIR - make the
# evaluator importable regardless of CWD.
ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "evaluator"]