# Demo-scoped BigQuery. Assets and escalations live in separate datasets so the
# agent's dataViewer role cannot read eval_reports or any other dataset.

resource "google_bigquery_dataset" "data" {
  dataset_id = "agent_demo_data"
  location   = var.bq_location
}

resource "google_bigquery_table" "assets" {
  dataset_id          = google_bigquery_dataset.data.dataset_id
  table_id            = "assets"
  deletion_protection = false
  schema              = file("${path.module}/../dev/schemas/assets.json")
}

resource "google_bigquery_dataset" "ops" {
  dataset_id = "agent_demo_ops"
  location   = var.bq_location
  # No default expiration: an open escalation must outlive the 5-day compute window
  # only until the whole demo is destroyed.
}

resource "google_bigquery_table" "escalations" {
  dataset_id          = google_bigquery_dataset.ops.dataset_id
  table_id            = "agent_escalations"
  deletion_protection = false
  schema              = file("${path.module}/../dev/schemas/agent_escalations.json")
}
