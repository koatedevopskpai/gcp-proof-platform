# -----------------------------------------------------------------------------
# FinOps cost guardrail - hard budget scoped to this workload's label.
#
# NOTE: GCP budgets use the BILLING ACCOUNT's currency. This account is GBP-
# denominated, so the cap is expressed in GBP (~15 GBP is approx the requested
# $20/month).
# -----------------------------------------------------------------------------

resource "google_monitoring_notification_channel" "budget" {
  display_name = "budget-alerts"
  type         = "email"
  labels = {
    email_address = var.budget_alerts_email
  }
}

resource "google_billing_budget" "budget" {
  billing_account = var.billing_account_id
  display_name    = "gcp-proof-platform-${var.environment}-monthly"

  amount {
    specified_amount {
      units = var.budget_limit_gbp
    }
  }

  budget_filter {
    projects        = ["projects/${data.google_project.current.number}"]
    calendar_period = "MONTH"

    # Scope to THIS workload only, via the FinOps label.
    labels = {
      workload = var.workload
    }
  }

  threshold_rules {
    threshold_percent = 0.8
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.budget.id]
  }
}