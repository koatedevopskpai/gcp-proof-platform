# -----------------------------------------------------------------------------
# Monitoring & Observability - Cloud Monitoring service, availability SLO,
# uptime check, alert policy, and a dashboard. Cloud Logging is on by default.
# -----------------------------------------------------------------------------

resource "google_monitoring_service" "app" {
  service_id   = "gcp-proof-platform-app"
  display_name = "gcp-proof-platform gateway"

  basic_service {
    service_type = "APP_ENGINE"
    service_labels = {
      module_id = "gateway"
    }
  }
}

# Availability SLO: 99% over a rolling 30 days.
resource "google_monitoring_slo" "availability" {
  service      = google_monitoring_service.app.service_id
  slo_id       = "availability-99"
  display_name = "99% availability (rolling 30 days)"

  goal                = 0.99
  rolling_period_days = 30

  basic_sli {
    availability {
      enabled = true
    }
  }
}

# Uptime check against the live gateway - generates real availability metrics
# (unlike the synthetic SLO, this produces actual traffic + data).
resource "google_monitoring_uptime_check_config" "gateway" {
  display_name = "gateway health"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/health"
    port         = 3002
    use_ssl      = false
    validate_ssl = false
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      host = google_compute_address.app.address
    }
  }
}

# Alert when the gateway health check fails (5 min window).
resource "google_monitoring_alert_policy" "gateway_down" {
  display_name = "gcp-proof-platform gateway down"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failed for 5m"

    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.gateway.uptime_check_id}\""
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1
    }
  }

  alert_strategy {
    auto_close = "3600s"
  }

  notification_channels = [google_monitoring_notification_channel.budget.id]
}

# Simple ops dashboard for the platform (uptime success ratio).
resource "google_monitoring_dashboard" "platform" {
  dashboard_json = <<EOF
{
  "displayName": "gcp-proof-platform",
  "gridLayout": {
    "columns": "2",
    "widgets": [
      {
        "title": "Gateway uptime (last 1h)",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.labels.host=\"${google_compute_address.app.address}\""
              }
            }
          }],
          "yAxis": { "label": "pass ratio", "scale": "LINEAR" }
        }
      },
      {
        "title": "SLO availability",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "metric.type=\"monitoring.googleapis.com/consumer/availability\" AND resource.labels.service_id=\"${google_monitoring_service.app.service_id}\""
              }
            }
          }],
          "yAxis": { "label": "availability", "scale": "LINEAR" }
        }
      }
    ]
  }
}
EOF
}