# -----------------------------------------------------------------------------
# Platform networking: custom VPC + subnets + Private Service Connect.
# Moves the always-on VM off the default network onto a dedicated,
# hardening-oriented VPC with private Google access.
#
# NOTE: Cloud NAT is intentionally NOT deployed here. It carries a flat hourly
# fee (~$9-35/mo) even when idle, which would push the always-on stack over the
# $20 budget - and the always-on VM egresses via its public IP anyway. The NAT
# pattern is documented in docs/architecture.md for private-only workloads.
# -----------------------------------------------------------------------------

resource "google_compute_network" "vpc" {
  name                    = "gcp-proof-platform-${var.environment}-vpc"
  auto_create_subnetworks = false
  description             = "gcp-proof-platform dedicated platform VPC (workload=${var.workload})"
}

resource "google_compute_subnetwork" "app" {
  name          = "gcp-proof-platform-${var.environment}-app"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = var.vpc_cidr

  # Instances can reach Google APIs over private Google access (no public IP
  # required for API egress).
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.0.32.0/20"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.0.64.0/20"
  }
}

# Private Service Connect - private, internal access to Google APIs
# (the "all-apis" service attachment) via an internal PSC endpoint.
#
# OPTIONAL (enable_psc). The GCP API in some environments rejects the bare
# "all-apis" forwarding-rule target via Terraform; this is kept as a guarded,
# documented pattern (see docs/architecture.md) rather than forcing the always-on
# stack to depend on it.
resource "google_compute_global_address" "psc" {
  count        = var.enable_psc ? 1 : 0
  name         = "gcp-proof-platform-${var.environment}-psc"
  purpose      = "PRIVATE_SERVICE_CONNECT"
  address_type = "INTERNAL"
  address      = "10.0.96.0"
  network      = google_compute_network.vpc.id
}

resource "google_compute_forwarding_rule" "psc" {
  count                 = var.enable_psc ? 1 : 0
  name                  = "gcp-proof-platform-${var.environment}-psc-googleapis"
  region                = var.region
  network               = google_compute_network.vpc.id
  ip_address            = google_compute_global_address.psc[0].id
  load_balancing_scheme = ""
  target                = "all-apis"
  labels = {
    workload = var.workload
  }
}

# Firewall rules moved onto the dedicated VPC.
resource "google_compute_firewall" "app_ingress" {
  name    = "gcp-proof-platform-${var.environment}-app"
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["3002", "8010", "8080"]
  }
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["gcp-proof-platform-app"]
}

resource "google_compute_firewall" "app_ssh" {
  name    = "gcp-proof-platform-${var.environment}-ssh"
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  source_ranges = var.ssh_cidr
  target_tags   = ["gcp-proof-platform-app"]
}