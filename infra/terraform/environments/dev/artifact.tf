resource "google_artifact_registry_repository" "images" {
  repository_id = "ai-platform"
  location      = var.region
  format        = "DOCKER"
  labels = {
    workload = var.workload
  }
}