# -----------------------------------------------------------------------------
# Eval pipeline reliability - alert when the daily eval-to-bq job fails.
# VM-free: uses Cloud Run job metrics, so it costs nothing while the always-on
# VM is down.
# -----------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "eval_job_failed" {
  display_name = "eval-to-bq job failed"
  combiner     = "OR"

  conditions {
    display_name = "eval-to-bq execution failed"

    condition_threshold {
      filter = join(" AND ", [
        "metric.type=\"run.googleapis.com/job/completed_execution_count\"",
        "resource.type=\"cloud_run_job\"",
        "resource.labels.job_name=\"${google_cloud_run_v2_job.eval_to_bq.name}\"",
        "metric.labels.result=\"failed\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.budget.name]

  alert_strategy {
    auto_close = "86400s"
  }

  depends_on = [google_cloud_run_v2_job.eval_to_bq]
}
