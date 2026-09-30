# -----------------------------------------------------------------------------
# Workload Identity Federation - GitHub Actions authenticates to GCP WITHOUT
# service-account keys, via an OIDC workload identity pool (same pattern as AWS
# OIDC federation). Attributes are mapped from the GitHub OIDC token.
#
# CI usage:
#   - auth: "google-github-actions/auth@v2" with workload_identity_provider =
#     projects/<project>/locations/global/workloadIdentityPools/github-pool/
#     providers/github-oidc
#   - service_account = ci@<project>.iam.gserviceaccount.com
# -----------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions pool"
  description               = "Workload identity federation for koatedevopskpai GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub Actions OIDC provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.actor"      = "assertion.actor"
  }

  attribute_condition = "assertion.repository_owner == 'koatedevopskpai'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# CI service account that GitHub Actions impersonates via WIF.
resource "google_service_account" "ci" {
  account_id   = "github-ci"
  display_name = "gcp-proof-platform GitHub Actions CI"
}

# Least-privilege: CI may push images + deploy Cloud Run jobs + run Cloud Build.
resource "google_project_iam_member" "ci_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_project_iam_member" "ci_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

# Allow the repository's GitHub Actions workflows to impersonate the CI SA.
resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/koatedevopskpai/gcp-proof-platform"
}