# Two Cloud Run services and one seed job. The agent is reachable from outside
# but requires IAM; rag-api is reachable only by the agent's service account.

resource "google_cloud_run_v2_service" "rag" {
  name                = "agent-demo-rag-api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.rag.email
    timeout         = "300s"

    containers {
      image = local.rag_image

      ports {
        container_port = 8000
      }

      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.demo.private_ip_address
      }
      env {
        name  = "DB_PORT"
        value = "5432"
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.aiplatform.name
      }
      env {
        name  = "DB_USER"
        value = google_sql_user.rag.name
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.rag_db.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "DB_AUTO_INIT"
        value = "false"
      }
      env {
        name  = "EMBEDDING_MODE"
        value = "vertex"
      }
      env {
        name  = "EMBEDDING_DIM"
        value = tostring(var.embedding_dim)
      }
      env {
        name  = "VERTEX_PROJECT"
        value = var.project_id
      }
      env {
        name  = "VERTEX_LOCATION"
        value = var.embedding_location
      }
      env {
        name  = "RAG_TOP_K"
        value = "4"
      }
      env {
        name  = "RAG_MIN_SCORE"
        value = "0.10"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.demo.id
        subnetwork = google_compute_subnetwork.demo.id
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.rag_db]
}

resource "google_cloud_run_v2_service" "agent" {
  name                = "agent-demo-adk"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.agent.email
    timeout         = "300s"

    containers {
      image = local.agent_image

      ports {
        container_port = 8080
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.vertex_location
      }
      env {
        name  = "AGENT_MODEL"
        value = var.agent_model
      }
      env {
        name  = "RAG_API_URL"
        value = google_cloud_run_v2_service.rag.uri
      }
      env {
        name  = "RAG_API_AUDIENCE"
        value = google_cloud_run_v2_service.rag.uri
      }
      env {
        name  = "ASSETS_SOURCE"
        value = "bigquery"
      }
      env {
        name  = "ESCALATION_SINK"
        value = "bigquery"
      }
      env {
        name  = "BQ_PROJECT"
        value = var.project_id
      }
      env {
        name  = "ASSETS_DATASET"
        value = google_bigquery_dataset.data.dataset_id
      }
      env {
        name  = "ESCALATIONS_DATASET"
        value = google_bigquery_dataset.ops.dataset_id
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }

    scaling {
      # In-memory ADK sessions: one instance avoids split session state.
      min_instance_count = 0
      max_instance_count = 1
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "agent_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "rag_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.rag.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agent.email}"
}

# One-off schema/seed job. It runs as the admin DB user, creates pgvector and the
# documents table, grants CRUD to the app user, then embeds and inserts the corpus.
resource "google_cloud_run_v2_job" "seed" {
  name                = "agent-demo-seed"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.seed.email
      timeout         = "1800s"
      max_retries     = 0

      containers {
        image   = local.rag_image
        command = ["python", "scripts/seed_cloudsql.py"]

        env {
          name  = "DB_HOST"
          value = google_sql_database_instance.demo.private_ip_address
        }
        env {
          name  = "DB_PORT"
          value = "5432"
        }
        env {
          name  = "DB_NAME"
          value = google_sql_database.aiplatform.name
        }
        env {
          name  = "DB_USER"
          value = google_sql_user.postgres.name
        }
        env {
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.seed_db.secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "DB_AUTO_INIT"
          value = "false"
        }
        env {
          name  = "APP_DB_USER"
          value = google_sql_user.rag.name
        }
        env {
          name  = "EMBEDDING_MODE"
          value = "vertex"
        }
        env {
          name  = "EMBEDDING_DIM"
          value = tostring(var.embedding_dim)
        }
        env {
          name  = "VERTEX_PROJECT"
          value = var.project_id
        }
        env {
          name  = "VERTEX_LOCATION"
          value = var.embedding_location
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = google_compute_network.demo.id
          subnetwork = google_compute_subnetwork.demo.id
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.seed_db]
}
