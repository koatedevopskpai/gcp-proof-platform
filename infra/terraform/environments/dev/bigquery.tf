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
  dataset_id          = google_bigquery_dataset.ai_platform.dataset_id
  table_id            = "eval_reports"
  deletion_protection = false
  schema              = file("${path.module}/schemas/eval_reports.json")
}

# -----------------------------------------------------------------------------
# ADK agent data plane.
#
# Assets are read-only to the agent. Escalations live in their own dataset so the
# service account can be granted dataEditor there without write access to the
# asset register or the evaluation reports.
#
# agent_ops deliberately has no default table expiration: an escalation with
# status=open must not disappear because it inherited the eval dataset's 90-day
# retention.
# -----------------------------------------------------------------------------

resource "google_bigquery_dataset" "agent_ops" {
  dataset_id = "agent_ops"
  location   = var.bq_location
  labels = {
    workload = var.workload
  }
}

resource "google_bigquery_table" "assets" {
  dataset_id          = google_bigquery_dataset.ai_platform.dataset_id
  table_id            = "assets"
  deletion_protection = false
  schema              = file("${path.module}/schemas/assets.json")
}

resource "google_bigquery_table" "agent_escalations" {
  dataset_id          = google_bigquery_dataset.agent_ops.dataset_id
  table_id            = "agent_escalations"
  deletion_protection = false
  schema              = file("${path.module}/schemas/agent_escalations.json")
}