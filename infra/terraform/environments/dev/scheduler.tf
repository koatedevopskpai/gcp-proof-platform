# -----------------------------------------------------------------------------
# Cloud Scheduler - run the evaluation pipeline daily (HTTP trigger to the
# Cloud Run job with OIDC auth).
# -----------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "eval_daily" {
  count = var.enable_scheduler ? 1 : 0

  name      = "eval-daily"
  schedule  = "0 6 * * *"
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.eval_to_bq.name}:run"

    oauth_token {
      service_account_email = google_service_account.eval_sa.email
    }
  }
}