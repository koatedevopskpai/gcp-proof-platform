# -----------------------------------------------------------------------------
# Evaluation trace storage and the provider credential.
#
# Traces are the source of truth for a scoring run (see services/evaluator/evaluator/
# trace_store.py): one JSONL object per run, keyed by run id. The BigQuery row carries
# only the pointer.
#
# The judge key is created as an empty secret. Terraform never holds the value: put the
# key in with `gcloud secrets versions add <secret> --data-file=-`, then set
# enable_judge = true so the job mounts it.
# -----------------------------------------------------------------------------

locals {
  trace_bucket = var.trace_bucket_name != "" ? var.trace_bucket_name : "${var.project_id}-eval-traces"
}

resource "google_storage_bucket" "eval_traces" {
  name                        = local.trace_bucket
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true

  labels = {
    workload = var.workload
  }
}

# Write-only: the job never reads traces back, so objectCreator is enough.
resource "google_storage_bucket_iam_member" "eval_traces_writer" {
  bucket = google_storage_bucket.eval_traces.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.eval_sa.email}"
}

resource "google_secret_manager_secret" "judge_api_key" {
  secret_id = var.judge_secret_id

  replication {
    auto {}
  }

  labels = {
    workload = var.workload
  }
}

resource "google_secret_manager_secret_iam_member" "eval_sa_accessor" {
  count = var.enable_judge ? 1 : 0

  secret_id = google_secret_manager_secret.judge_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.eval_sa.email}"
}
