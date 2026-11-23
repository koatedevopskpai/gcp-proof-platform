# Cloud SQL Postgres with pgvector, private IP only. The app user has normal
# privileges; a separate seed_admin (cloudsqlsuperuser) creates the extension and
# schema, then grants only CRUD on documents to the app user.

resource "random_password" "rag" {
  length  = 32
  special = false
}

resource "random_password" "seed_admin" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "demo" {
  name                = "agent-demo-pg"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = false

  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_size         = var.db_disk_size
    disk_type         = "PD_SSD"
    disk_autoresize   = false

    backup_configuration {
      enabled = false
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.demo.id
    }
  }

  depends_on = [google_service_networking_connection.sql]

  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }
}

resource "google_sql_database" "aiplatform" {
  name     = "aiplatform"
  instance = google_sql_database_instance.demo.name
}

resource "google_sql_user" "rag" {
  name     = "rag"
  instance = google_sql_database_instance.demo.name
  password = random_password.rag.result
}

resource "google_sql_user" "postgres" {
  # Cloud SQL creates the postgres user with the instance. If this resource fails
  # with a 409 on the first apply, import it and re-apply:
  #   terraform import google_sql_user.postgres <project>/<instance>/postgres
  name     = "postgres"
  instance = google_sql_database_instance.demo.name
  password = random_password.seed_admin.result
}

resource "google_secret_manager_secret" "rag_db" {
  secret_id = "agent-demo-rag-db"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "rag_db" {
  secret      = google_secret_manager_secret.rag_db.id
  secret_data = random_password.rag.result
}

resource "google_secret_manager_secret" "seed_db" {
  secret_id = "agent-demo-seed-db"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "seed_db" {
  secret      = google_secret_manager_secret.seed_db.id
  secret_data = random_password.seed_admin.result
}
