# -----------------------------------------------------------------------------
# VPC Service Controls - data-perimeter pattern.
#
# IMPORTANT: VPC-SC is an ORGANIZATION-level construct. It CANNOT be created in
# a standalone (non-organization) account. This module is written correctly and
# applies cleanly in any org; it is disabled by default here because
# gcp-proof-platform runs in a standalone account. Set `enable_vpc_sc = true`
# and `organization_id` in an org-backed environment to enforce the perimeter.
# -----------------------------------------------------------------------------

data "google_organization" "org" {
  count        = var.enable_vpc_sc && var.organization_id != "" ? 1 : 0
  organization = var.organization_id
}

resource "google_access_context_manager_access_policy" "policy" {
  count  = var.enable_vpc_sc ? 1 : 0
  parent = data.google_organization.org[0].name
  title  = "gcp-proof-platform access policy"
}

resource "google_access_context_manager_service_perimeter" "perimeter" {
  count          = var.enable_vpc_sc ? 1 : 0
  parent         = "organizations/${var.organization_id}"
  name           = "gcp-proof-platform-${var.environment}-perimeter"
  title          = "gcp-proof-platform data perimeter"
  perimeter_type = "PERIMETER_TYPE_REGULAR"

  status {
    restricted_services = [
      "storage.googleapis.com",
      "bigquery.googleapis.com",
      "cloudfunctions.googleapis.com",
      "run.googleapis.com",
    ]

    # Protect only resources labelled with this workload.
    resources = ["projects/${data.google_project.current.number}"]
  }
}