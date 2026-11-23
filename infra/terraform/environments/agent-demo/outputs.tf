output "agent_url" {
  description = "Cloud Run agent URL (requires an ID token)"
  value       = google_cloud_run_v2_service.agent.uri
}

output "rag_url" {
  description = "rag-api URL (requires an ID token; only the agent SA is granted invoker)"
  value       = google_cloud_run_v2_service.rag.uri
}

output "db_instance" {
  value = google_sql_database_instance.demo.name
}

output "db_private_ip" {
  value = google_sql_database_instance.demo.private_ip_address
}

output "seed_job" {
  value = google_cloud_run_v2_job.seed.name
}

output "assets_dataset" {
  value = google_bigquery_dataset.data.dataset_id
}

output "escalations_dataset" {
  value = google_bigquery_dataset.ops.dataset_id
}

output "teardown" {
  description = "Destroy this root at the end of the five-day window"
  value       = "terraform -chdir=infra/terraform/environments/agent-demo destroy"
}
