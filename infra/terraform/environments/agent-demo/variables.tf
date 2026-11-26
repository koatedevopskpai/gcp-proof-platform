variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "bq_location" {
  type    = string
  default = "US"
}

variable "db_tier" {
  description = "Cloud SQL tier. db-g1-small is about $6 for five days; db-f1-micro is cheaper but shared-core"
  type        = string
  default     = "db-g1-small"
}

variable "db_disk_size" {
  type    = number
  default = 10
}

variable "agent_invoker" {
  description = "User or group allowed to invoke the agent; added as roles/run.invoker on that service only"
  type        = string
}

variable "agent_model" {
  type    = string
  default = "gemini-3-flash-preview"
}

variable "vertex_location" {
  description = "Location for Gemini (global-only for gemini-3-flash-preview)"
  type        = string
  default     = "global"
}

variable "embedding_location" {
  type    = string
  default = "us-central1"
}

variable "embedding_dim" {
  type    = number
  default = 384
}

variable "agent_image" {
  description = "Optional full image reference; defaults to the Artifact Registry path and the agent-demo tag"
  type        = string
  default     = ""
}

variable "rag_image" {
  description = "Optional full image reference; defaults to the Artifact Registry path and the agent-demo tag"
  type        = string
  default     = ""
}
