FROM python:3.12-slim

# Pull patched base packages so the Trivy HIGH/CRITICAL gate passes. The first CI
# run found zlib1g CVE-2026-85091 in this image family.
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY support_agent ./support_agent

# Cloud Run expects the process to listen on $PORT. ADK's server is deliberately
# unauthenticated; Cloud Run IAM is the authentication layer (no allUsers invoker).
ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "adk api_server --host 0.0.0.0 --port ${PORT} /app"]
