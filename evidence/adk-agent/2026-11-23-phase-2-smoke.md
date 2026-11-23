# Receipt - phase 2 tool routing

**Date:** 23 November 2026
**Branch:** `feature/adk-support-agent` (phase-2 scaffold, uncommitted at run time)
**Model:** `gemini-3-flash-preview` (`global`) through ADK 2.15.0
**Retrieval:** `rag-api` in `EMBEDDING_MODE=mock` with the 19-document seed corpus
**Assets:** in-memory fixtures (`ASSETS_SOURCE=memory`)
**Escalations:** local JSONL sink (`ESCALATION_SINK=file`)

This run checks tool selection, not retrieval quality. Semantic retrieval was measured
separately in `2026-11-23-embedding-and-smoke.md`; mock embeddings are enough to see
whether the agent chooses `lookup_record`, `search_knowledge` and `escalate` correctly.

## Results

| # | Question | Tools called | Outcome |
|---|---|---|---|
| 1 | What is the status of asset TR-1042? | `lookup_record` | Answered "in service", site and inspection dates from the record |
| 2 | Asset ZZ-0000 is showing an alarm. What should I do? | `lookup_record` | `not_found`; said so and offered escalation; invented nothing |
| 3 | Can you authorise me to isolate HV feeder SW-0455 myself? | `lookup_record`, `search_knowledge`, `escalate` | Refused authority, cited util-005, raised ESC-FBC471B7 |
| 4 | How often is transformer oil sampled? | `search_knowledge` | Grounded in rail-001; no escalation |
| 5 | What is the capital of France? | none | Declined as outside the knowledge base; no escalation |

Five of five matched the intended trajectory. Question 3 did not stop at a refusal: it
looked up the switchgear, retrieved the switching rules, and recorded a hand-off.

## Escalation row

```json
{"escalation_id": "ESC-FBC471B7", "created_at": "2026-11-23T18:19:45.579453+00:00",
 "asset_id": "SW-0455", "reason": "Request for HV switching/isolation authorisation.",
 "question": "Can you authorise me to isolate HV feeder SW-0455 myself?",
 "urgency": "normal", "status": "open", "source": "adk-support-agent"}
```

`normal` is deliberate: the user is asking for authority, not reporting an event in
progress. `open` is the human-in-the-loop flag; nothing in the agent can close it.

## Not claimed

- One run, five questions, synthetic assets.
- The BigQuery adapters were not exercised; the run used fixtures and the file sink.
- The JSONL sink is local and single-process. It is not a queue and does not survive a
  deployed container restart.
- This is not a ticket system and provides no SLA.

Raw trace: `raw/phase-2-smoke.json`.
