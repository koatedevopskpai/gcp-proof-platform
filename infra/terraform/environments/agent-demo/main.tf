terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "gcs" {
    bucket = "gcp-proof-platform-tfstate"
    prefix = "agent-demo"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  user_project_override = true
  billing_project       = var.project_id

  default_labels = {
    project             = var.project_id
    environment         = "agent-demo"
    managed_by          = "terraform"
    cost_center         = "cc-gcp-platform"
    workload            = "gcp-proof-platform"
    cost_category       = "engineering-rnd"
    data_classification = "public-reference"
    expires             = "5-days"
  }
}

data "google_project" "current" {}

locals {
  repo        = "us-central1-docker.pkg.dev/${var.project_id}/ai-platform"
  agent_image = var.agent_image != "" ? var.agent_image : "${local.repo}/adk-agent:agent-demo"
  rag_image   = var.rag_image != "" ? var.rag_image : "${local.repo}/rag-api:agent-demo"
}

# The demo enables only what it needs. disable_on_destroy = false keeps the APIs
# available for the rest of the project when the demo is torn down.
resource "google_project_service" "apis" {
  for_each = toset([
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}
