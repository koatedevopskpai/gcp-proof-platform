# -----------------------------------------------------------------------------
# Cloud Scheduler - run the evaluation pipeline daily (HTTP trigger to the
# Cloud Run job with OIDC auth).
# -----------------------------------------------------------------------------

resource "google_cloud_scheduler_job" "eval_daily" {
  count = var.enable_scheduler ? 1 : 0

  name      = "eval-daily"
  schedule  = "0 6 * * *"
  time_zone = "UTC"

  # The job can run up to 600s; give the trigger matching headroom.
  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.eval_to_bq.name}:run"

    oauth_token {
      service_account_email = google_service_account.eval_sa.email
    }
  }

  # The job must exist before the scheduler can reference its :run endpoint.
  depends_on = [google_cloud_run_v2_job.eval_to_bq]
}

# Cloud Scheduler mints an OAuth token for eval_sa, so its service agent needs
# Token Creator on that SA. Without this the trigger returns PERMISSION_DENIED.
resource "google_service_account_iam_member" "scheduler_token_creator" {
  count = var.enable_scheduler ? 1 : 0

  service_account_id = google_service_account.eval_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}