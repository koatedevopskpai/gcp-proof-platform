# -----------------------------------------------------------------------------
# BigQuery - analytics plane for the MLOps evaluation reports.
# -----------------------------------------------------------------------------

resource "google_bigquery_dataset" "ai_platform" {
  dataset_id                  = "ai_platform"
  location                    = var.bq_location
  default_table_expiration_ms = 90 * 24 * 3600 * 1000 # 90 days
  labels = {
    workload = var.workload
  }
}

resource "google_bigquery_table" "eval_reports" {
  dataset_id = google_bigquery_dataset.ai_platform.dataset_id
  table_id   = "eval_reports"
  schema     = file("${path.module}/schemas/eval_reports.json")
}