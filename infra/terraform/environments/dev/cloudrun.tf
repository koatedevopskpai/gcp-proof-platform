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

resource "google_cloud_run_v2_job" "eval_to_bq" {
  name     = "eval-to-bq"
  location = var.region

  template {
    template {
      timeout = "600s"

      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/ai-platform/eval-to-bq:latest"

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
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