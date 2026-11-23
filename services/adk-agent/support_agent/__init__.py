"""ADK support agent for the GCP proof platform.

Prototype status. The agent answers questions over the asset knowledge base served
by `rag-api`, looks up single records in the asset register, and escalates requests
it cannot resolve. Phase 2 runs against local fixtures and a JSONL escalation sink;
the BigQuery adapters are selected with `ASSETS_SOURCE=bigquery` and
`ESCALATION_SINK=bigquery`.
"""
