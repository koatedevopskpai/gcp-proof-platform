# -----------------------------------------------------------------------------
# GKE (OPTIONAL, DISABLED BY DEFAULT).
#
# The GKE management fee is ~$73/mo, so it does NOT fit the $20 always-on budget.
# This module exists to demonstrate GKE + Helm skills on-demand: set
# enable_gke = true, deploy, demo, then destroy (or terraform apply again with
# enable_gke = false). Use with infra/helm charts in this repo.
# -----------------------------------------------------------------------------

resource "google_container_cluster" "primary" {
  count    = var.enable_gke ? 1 : 0
  name     = "gcp-proof-platform-${var.environment}"
  location = var.region

  initial_node_count = 1

  node_config {
    machine_type = "e2-small"
    labels = {
      workload    = var.workload
      cost_center = var.cost_center
    }
  }

  deletion_protection = false

  # Keep the always-on budget safe: no autoscaling beyond the demo node.
  remove_default_node_pool = false
}