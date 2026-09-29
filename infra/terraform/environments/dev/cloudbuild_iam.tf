# Cloud Build needs permissions to push to Artifact Registry and deploy.
# Use an explicit, purpose-built SA (legacy <project>@cloudbuild.gserviceaccount.com
# is not always auto-created on new projects). Submit builds with:
#   gcloud builds submit --service-account=cloudbuild@gcp-proof-platform.iam.gserviceaccount.com
resource "google_service_account" "cloudbuild" {
  account_id   = "cloudbuild"
  display_name = "gcp-proof-platform Cloud Build"
}

locals {
  cloudbuild_sa = google_service_account.cloudbuild.email
}

resource "google_project_iam_member" "cloudbuild_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}

resource "google_project_iam_member" "cloudbuild_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}

resource "google_project_iam_member" "cloudbuild_iam_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}

resource "google_project_iam_member" "cloudbuild_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}

resource "google_project_iam_member" "cloudbuild_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${local.cloudbuild_sa}"
}