variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "instance_type" {
  description = "Always-on VM type (e2-small=2GB)"
  type        = string
  default     = "e2-small"
}

variable "root_volume_size" {
  type    = number
  default = 30
}

variable "repo_url" {
  description = "Public git URL of the gcp-proof-platform repo"
  type        = string
  default     = "https://github.com/koatedevopskpai/gcp-proof-platform.git"
}

variable "ssh_cidr" {
  type        = list(string)
  description = "CIDRs allowed to reach SSH on the VM"
  default     = ["0.0.0.0/0"]
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "enable_gke" {
  description = "Provision the optional (ephemeral) GKE cluster - NOT part of the $20 always-on budget"
  type        = bool
  default     = false
}

variable "enable_scheduler" {
  description = "Schedule the eval-to-bq Cloud Run job daily"
  type        = bool
  default     = true
}

# --- FinOps tagging taxonomy ---
variable "cost_center" {
  type    = string
  default = "cc-gcp-platform"
}

variable "business_unit" {
  type    = string
  default = "data-platform"
}

variable "tag_owner" {
  type    = string
  default = "koatekpai"
}

variable "budget_owner" {
  type    = string
  default = "platform-leads"
}

variable "workload" {
  type    = string
  default = "gcp-proof-platform"
}

variable "cost_category" {
  type    = string
  default = "engineering-rnd"
}

variable "data_classification" {
  type    = string
  default = "public-reference"
}

# --- Budget & cost guardrails ---
variable "billing_account_id" {
  description = "GCP billing account id (e.g. 01FBBE-ACD618-CFA5D6)"
  type        = string
}

variable "budget_limit_gbp" {
  description = "Hard monthly budget cap in GBP (billing account is GBP-denominated; ~15 GBP is approx $20)"
  type        = number
  default     = 15
}

variable "budget_alerts_email" {
  type    = string
  default = "koatekpai@outlook.com"
}