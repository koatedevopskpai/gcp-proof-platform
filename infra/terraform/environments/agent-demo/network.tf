# Private network for Cloud Run egress and the Cloud SQL private IP.
# No NAT: the demo services reach Google APIs over the default route.

resource "google_compute_network" "demo" {
  name                    = "agent-demo-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "demo" {
  name                     = "agent-demo-subnet"
  network                  = google_compute_network.demo.id
  region                   = var.region
  ip_cidr_range            = "10.20.0.0/24"
  private_ip_google_access = true
}

# Private services access for Cloud SQL. The range must not overlap the subnet.
resource "google_compute_global_address" "sql" {
  name          = "agent-demo-sql-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.demo.id
}

resource "google_service_networking_connection" "sql" {
  network                 = google_compute_network.demo.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql.name]
  depends_on              = [google_project_service.apis]
}
