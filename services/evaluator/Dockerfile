FROM python:3.12-slim

# Pull patched base packages so the Trivy HIGH/CRITICAL gate passes (zlib1g
# CVE-2026-85091 is fixed in a Debian point release).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

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