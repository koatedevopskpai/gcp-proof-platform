# One service account per workload. No project Editor, no keys, no allUsers.

resource "google_service_account" "agent" {
  account_id   = "agent-demo-agent"
  display_name = "ADK agent (agent demo)"
}

resource "google_service_account" "rag" {
  account_id   = "agent-demo-rag"
  display_name = "rag-api (agent demo)"
}

resource "google_service_account" "seed" {
  account_id   = "agent-demo-seed"
  display_name = "Cloud SQL seed job (agent demo)"
}

# The human does not invoke the agent directly. They can mint an ID token for this
# service account, which has exactly one role: run.invoker on the agent service.
resource "google_service_account" "invoker" {
  account_id   = "agent-demo-invoker"
  display_name = "Agent demo invoker"
}

resource "google_service_account_iam_member" "user_can_mint_invoker_token" {
  service_account_id = google_service_account.invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:${var.agent_invoker}"
}

# --- Vertex AI: the only model access any of them has ---
resource "google_project_iam_member" "agent_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_project_iam_member" "rag_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.rag.email}"
}

resource "google_project_iam_member" "seed_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.seed.email}"
}

# --- Logs ---
resource "google_project_iam_member" "agent_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_project_iam_member" "rag_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.rag.email}"
}

resource "google_project_iam_member" "seed_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.seed.email}"
}

# --- Artifact Registry: pull only, on the existing repository ---
resource "google_artifact_registry_repository_iam_member" "agent_reader" {
  project    = var.project_id
  location   = var.region
  repository = "ai-platform"
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_artifact_registry_repository_iam_member" "rag_reader" {
  project    = var.project_id
  location   = var.region
  repository = "ai-platform"
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.rag.email}"
}

resource "google_artifact_registry_repository_iam_member" "seed_reader" {
  project    = var.project_id
  location   = var.region
  repository = "ai-platform"
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.seed.email}"
}

# --- BigQuery: read one dataset, write one dataset, no project-wide data role ---
resource "google_project_iam_member" "agent_bq_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_bigquery_dataset_iam_member" "agent_assets_viewer" {
  dataset_id = google_bigquery_dataset.data.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_bigquery_dataset_iam_member" "agent_escalations_editor" {
  dataset_id = google_bigquery_dataset.ops.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.agent.email}"
}

# --- Secrets: the app password only to rag-api; the admin password only to the seed job ---
resource "google_secret_manager_secret_iam_member" "rag_db" {
  secret_id = google_secret_manager_secret.rag_db.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.rag.email}"
}

resource "google_secret_manager_secret_iam_member" "seed_db" {
  secret_id = google_secret_manager_secret.seed_db.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.seed.email}"
}
