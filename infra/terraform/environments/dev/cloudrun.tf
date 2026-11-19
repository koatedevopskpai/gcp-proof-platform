# -----------------------------------------------------------------------------
# Cloud Run job - scheduled evaluation pipeline that loads reports into BigQuery.
# Demonstrates Cloud Run (jobs) + the BigQuery data pipeline on the MLOps plane.
# -----------------------------------------------------------------------------

resource "google_service_account" "eval_sa" {
  account_id   = "eval-to-bq"
  display_name = "eval-to-bq Cloud Run job"
}

resource "google_project_iam_member" "eval_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.eval_sa.email}"
}

resource "google_project_iam_member" "eval_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.eval_sa.email}"
}

# Without this the job's container cannot pull the image from Artifact Registry.
resource "google_project_iam_member" "eval_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.eval_sa.email}"
}

resource "google_cloud_run_v2_job" "eval_to_bq" {
  name     = "eval-to-bq"
  location = var.region

  template {
    template {
      # RAGAS + pandas + langchain; traced runs of ten cases took ~140 s locally.
      timeout = "1800s"

      # A quality gate fails deterministically: retrying a failed evaluation only
      # repeats the judge spend and rewrites the same BigQuery rows. Cloud Run
      # defaults to 3 retries, so this must be explicit.
      max_retries = 0

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/ai-platform/eval-to-bq:latest"

        resources {
          limits = {
            cpu    = "2"
            memory = "2Gi"
          }
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BQ_DATASET"
          value = google_bigquery_dataset.ai_platform.dataset_id
        }
        env {
          name  = "BQ_TABLE"
          value = google_bigquery_table.eval_reports.table_id
        }
        env {
          name  = "JUDGE_MODEL"
          value = var.judge_model
        }
        env {
          name  = "SCORING_ARM"
          value = var.scoring_arm
        }
        env {
          name  = "VERTEX_PROJECT"
          value = var.project_id
        }
        env {
          name  = "VERTEX_MODEL"
          value = var.vertex_model
        }
        env {
          name  = "VERTEX_LOCATION"
          value = var.vertex_location
        }
        env {
          name  = "VERTEX_EMBEDDING_LOCATION"
          value = var.vertex_embedding_location
        }
        env {
          name  = "RAGAS_ENABLED"
          value = var.enable_ragas ? "1" : "0"
        }
        env {
          name  = "TRACE_BUCKET"
          value = google_storage_bucket.eval_traces.name
        }
        env {
          name  = "TRACE_LOCAL_DIR"
          value = "/tmp/traces"
        }

        # The credential is a secret reference, never an inline value: an env { value }
        # would put the key in Terraform state and in the Cloud Run revision.
        dynamic "env" {
          for_each = var.enable_judge ? [1] : []
          content {
            name = "OPENAI_API_KEY"
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.judge_api_key.secret_id
                version = "latest"
              }
            }
          }
        }
      }

      service_account = google_service_account.eval_sa.email
    }
  }

  labels = {
    workload = var.workload
  }

  # Ephemeral/rebuildable job - allow destroy + recreate.
  deletion_protection = false
}