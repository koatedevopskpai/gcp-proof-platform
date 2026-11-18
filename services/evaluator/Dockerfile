FROM python:3.12-slim

# The image has no git, so stamp the commit at build time; reports record it in provenance.
ARG GIT_COMMIT=""
ENV GIT_COMMIT=$GIT_COMMIT

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY evaluator ./evaluator
COPY datasets ./datasets

# Cloud Build runs steps from /workspace, not the image WORKDIR - make the
# evaluator importable regardless of CWD.
ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "evaluator"]