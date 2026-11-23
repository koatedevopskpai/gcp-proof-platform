# Agent demo (five days)

A self-contained Terraform root for a five-day, keyless deployment of the ADK agent.
It is isolated from `environments/dev`: its own VPC, Cloud SQL, Cloud Run services,
datasets and secrets, with its own state prefix (`agent-demo`). Destroying this root
removes the demo; the evaluation path in `dev` is untouched.

```
you / invoker SA
      |
      v
Cloud Run: agent-demo-adk  (ingress all, IAM required)
      |  ID token (audience = rag URL)
      v
Cloud Run: agent-demo-rag-api  (IAM required, only the agent SA can invoke)
      |  private IP
      v
Cloud SQL Postgres 16 (pgvector, no public IP)
```

The agent calls Vertex AI and BigQuery as its own service account. No service
account keys and no `GOOGLE_API_KEY` exist.

## Bring it up

```powershell
# Images (local build or Cloud Build)
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/<project>/ai-platform/rag-api:agent-demo services/rag-api
docker build -t us-central1-docker.pkg.dev/<project>/ai-platform/adk-agent:agent-demo services/adk-agent
docker push us-central1-docker.pkg.dev/<project>/ai-platform/rag-api:agent-demo
docker push us-central1-docker.pkg.dev/<project>/ai-platform/adk-agent:agent-demo

cd infra/terraform/environments/agent-demo
Copy-Item terraform.tfvars.example terraform.tfvars   # set agent_invoker
terraform init
terraform apply
```

After the apply:

```powershell
# 1. Create pgvector, the documents table, grant the app user, embed and seed the corpus
gcloud run jobs execute agent-demo-seed --region=us-central1 --wait

# 2. Load the synthetic asset rows into agent_demo_data.assets
python services/adk-agent/scripts/seed_assets.py --project <project> --dataset agent_demo_data
```

The `rag-api` service uses a build tag. Cloud Run resolves a tag to a digest when the
service is created or updated; after pushing a new image under the same tag, run:

```powershell
gcloud run services update agent-demo-rag-api --region=us-central1 \
  --image=us-central1-docker.pkg.dev/<project>/ai-platform/rag-api:agent-demo
```

## Invoke

The human cannot call the agent directly. They can mint an ID token for
`agent-demo-invoker`, which has exactly one role: `roles/run.invoker` on the agent.

```powershell
$url = terraform output -raw agent_url
$token = gcloud auth print-identity-token `
  --impersonate-service-account=agent-demo-invoker@<project>.iam.gserviceaccount.com `
  --audiences=$url

# create a session, then run
curl.exe -H "Authorization: Bearer $token" -H "Content-Type: application/json" `
  --data-binary '{"sessionId":"demo1"}' `
  "$url/apps/support_agent/users/demo/sessions"

curl.exe -H "Authorization: Bearer $token" -H "Content-Type: application/json" `
  --data-binary '{"appName":"support_agent","userId":"demo","sessionId":"demo1","newMessage":{"role":"user","parts":[{"text":"What is the status of asset TR-1042?"}]}}' `
  "$url/run"
```

`iamcredentials.googleapis.com` must be enabled; Terraform does this. The token
creator role is granted only on the invoker service account, not on the agent's
runtime account.

## Destroy (day 5)

```powershell
.\scripts\agent-demo-down.ps1
```

This removes Cloud Run, Cloud SQL, the VPC, `agent_demo_data`, `agent_demo_ops`, the
secrets and the service accounts. The container images remain in Artifact Registry
(cents). Do not leave the Cloud SQL instance running after the window: it bills even
when idle.

## Cost

`db-g1-small`, zonal, no HA, no backups, 10 GB SSD. Roughly **$6–9 for five days**
(Cloud SQL is the dominant cost; Cloud Run scales to zero). The existing budget alert
is £15/month, so this stays well under it.

## Notes

- `rag-api` has public ingress but no `allUsers`; requests without an ID token get
  `403`. Only the agent service account has `run.invoker`.
- The ADK API server has no authentication of its own. Cloud Run IAM is the boundary.
- Sessions are in-memory, so the agent is capped at one instance.
- The database uses a password in Secret Manager (app and seed each have their own
  secret) rather than IAM database auth. The Cloud SQL Python connector supports
  `pg8000`/`pymysql`/`pytds`, not `psycopg`; switching drivers would have changed the
  retrieval stack for a five-day demo. The agent and all GCP API calls are keyless.
