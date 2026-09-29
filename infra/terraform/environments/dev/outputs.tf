output "vm_ip" {
  description = "Public IP of the always-on VM"
  value       = google_compute_address.app.address
}

output "url" {
  description = "Always-on gateway URL"
  value       = "http://${google_compute_address.app.address}:3002"
}

output "health_url" {
  value = "http://${google_compute_address.app.address}:3002/health"
}

output "ssh_command" {
  value = "gcloud compute ssh ${google_compute_instance.app.name} --zone ${var.zone} --project ${var.project_id}"
}

output "bq_dataset" {
  value = google_bigquery_dataset.ai_platform.dataset_id
}

output "eval_job" {
  value = google_cloud_run_v2_job.eval_to_bq.name
}

output "gke_cluster" {
  description = "Optional ephemeral GKE cluster (empty when enable_gke=false)"
  value       = var.enable_gke ? google_container_cluster.primary[0].name : ""
}