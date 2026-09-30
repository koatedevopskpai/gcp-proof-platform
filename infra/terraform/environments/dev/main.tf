terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    bucket = "gcp-proof-platform-tfstate"
    prefix = "dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  # --- FinOps tagging taxonomy (applied to every labelled resource) ---
  default_labels = {
    project             = var.project_id
    environment         = var.environment
    managed_by          = "terraform"
    cost_center         = var.cost_center
    business_unit       = var.business_unit
    owner               = var.tag_owner
    budget_owner        = var.budget_owner
    workload            = var.workload
    cost_category       = var.cost_category
    data_classification = var.data_classification
  }
}

data "google_project" "current" {}

# -----------------------------------------------------------------------------
# Compute Engine - the always-on live stack (Docker Compose, same 4 services as
# the AWS project). Startup script clones the repo and brings the stack up.
# -----------------------------------------------------------------------------

resource "google_compute_address" "app" {
  name   = "gcp-proof-platform-${var.environment}-app"
  region = var.region
}

resource "google_compute_instance" "app" {
  name         = "gcp-proof-platform-${var.environment}-app"
  machine_type = var.instance_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "projects/debian-cloud/global/images/family/debian-12"
      size  = var.root_volume_size
      type  = "pd-balanced"
    }
  }

  network_interface {
    network    = google_compute_network.vpc.id
    subnetwork = google_compute_subnetwork.app.id
    access_config {
      nat_ip = google_compute_address.app.address
    }
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh.tftpl", {
    repo_url = var.repo_url
  })

  # Allow the provider to stop the instance when the network changes.
  allow_stopping_for_update = true

  service_account {
    scopes = ["cloud-platform"]
  }

  tags = ["gcp-proof-platform-app"]

  labels = {
    workload    = var.workload
    cost_center = var.cost_center
  }
}