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

variable "vpc_cidr" {
  description = "CIDR for the platform VPC app subnet"
  type        = string
  default     = "10.0.0.0/24"
}

variable "enable_vpc_sc" {
  description = "Apply VPC Service Controls perimeter (REQUIRES an organization; standalone accounts cannot use VPC-SC)"
  type        = bool
  default     = false
}

variable "enable_psc" {
  description = "Create the Private Service Connect endpoint to Google APIs (documented pattern; some environments reject the all-apis target via Terraform)"
  type        = bool
  default     = false
}

variable "organization_id" {
  description = "GCP organization id for VPC Service Controls (leave empty for standalone accounts)"
  type        = string
  default     = ""
}

variable "enable_gke" {
  description = "Provision the optional (ephemeral) GKE cluster - NOT part of the $20 always-on budget"
  type        = bool
  default     = false
}

variable "enable_scheduler" {
  description = "Run eval-to-bq daily. Off by default: a probabilistic report on a schedule is a recurring bill for no new signal. Invoke the job on demand or from Cloud Build instead."
  type        = bool
  default     = false
}

variable "enable_judge" {
  description = "Mount the provider credential into the eval job. Only needed when judge_arm = openai; requires a secret version"
  type        = bool
  default     = false
}

variable "judge_arm" {
  description = "Judge used for the gate's report: lexical (no model, free), vertex (runtime identity), or openai (needs the mounted key)"
  type        = string
  default     = "lexical"

  validation {
    condition     = contains(["lexical", "vertex", "openai"], var.judge_arm)
    error_message = "judge_arm must be lexical, vertex or openai."
  }
}

variable "judge_model" {
  description = "OpenAI judge model, used only when judge_arm = openai"
  type        = string
  default     = "gpt-4o-mini"
}

variable "scoring_arm" {
  description = "RAGAS scoring arm: vertex (runtime identity, no key) or openai (needs the mounted key)"
  type        = string
  default     = "vertex"

  validation {
    condition     = contains(["vertex", "openai"], var.scoring_arm)
    error_message = "scoring_arm must be vertex or openai."
  }
}

variable "vertex_model" {
  description = "Vertex AI judge model"
  type        = string
  default     = "gemini-3-flash-preview"
}

variable "vertex_location" {
  description = "Vertex AI location for the judge (gemini-3-flash-preview is global-only)"
  type        = string
  default     = "global"
}

variable "vertex_embedding_location" {
  description = "Vertex AI location for embeddings"
  type        = string
  default     = "us-central1"
}

variable "enable_ragas" {
  description = "Score with RAGAS and write a trace per run. The vertex arm needs no key; the openai arm needs enable_judge"
  type        = bool
  default     = true
}

variable "judge_secret_id" {
  description = "Secret Manager secret holding the provider API key"
  type        = string
  default     = "eval-judge-api-key"
}

variable "trace_bucket_name" {
  description = "GCS bucket for evaluation traces (defaults to <project>-eval-traces)"
  type        = string
  default     = ""
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
  description = "GCP billing account id (e.g. AAAAAA-BBBBBB-CCCCCC)"
  type        = string
}

variable "budget_limit_gbp" {
  description = "Monthly budget alert threshold in GBP (billing account is GBP-denominated; ~15 GBP is approx $20; alerts at 80% and 100%, does not cap spend)"
  type        = number
  default     = 15
}

variable "budget_alerts_email" {
  type    = string
  default = "koatekpai@outlook.com"
}