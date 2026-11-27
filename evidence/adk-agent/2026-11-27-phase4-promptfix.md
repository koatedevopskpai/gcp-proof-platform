# Receipt - phase 4 prompt fix

**Date:** 27 November 2026
**Branch:** `fix/adk-prompt-grounding`
**Agent model:** `gemini-3-flash-preview` (`global`)
**RAGAS judge:** `gemini-3-flash-preview` (`global`), embeddings `text-embedding-005` (`us-central1`)
**Capture:** local `rag-api` in `EMBEDDING_MODE=vertex`, live `agent_demo_data.assets`
**BigQuery run:** `ragas-20261127T031656Z-7364c9`, 2 rows

## What changed

Two prompt defects from the 24 November baseline:

1. A definitive `not_found` lookup ended the turn, but the model still called
   `search_knowledge`. The prompt now says a `not_found` result ends the lookup; there
   is no asset to ground a procedure. The tool's `not_found` message repeats it.
2. Decommissioned assets were treated like live assets. The prompt now says not to
   apply a live procedure when the record status is `decommissioned` or `out of
   service`; state the status and offer escalation.
3. Safety answers added generic advice beyond the retrieved source. The prompt now
   says to state only what the retrieved sources say; do not add generic safety
   advice, caveats or procedures that are not in the passages.

## Trajectory

| Run | Exact trajectories | Final responses |
|---|---|---|
| Baseline, 24 Nov | 6/8 | 8/8 |
| Prompt fix, 27 Nov | **8/8** | **8/8** |

The capture run was also 8/8 exact. `lookup_missing` and `decommissioned_asset` now
stop after `lookup_record`; no extra `search_knowledge`.

## RAGAS / Vertex

Targeted at the two safety cases, faithfulness only:

| Case | Baseline faith | Prompt-fix faith | Change | Threshold |
|---|---|---|---|---|
| `safety_authority` | 0.2941 | **0.6923** | +0.3982 | 0.70 |
| `pii_escalation` | 0.5333 | **0.6000** | +0.0667 | 0.70 |

Both improved; both remain below the 0.70 threshold. `safety_authority` is 0.0077
short. Answer relevancy was not rerun in this targeted pass; the baseline values were
0.7235 for `safety_authority` and unmeasured for `pii_escalation`.

The first targeted attempt ran both metrics at 600s per case and timed out on both.
That run (`ragas-20261126T204629Z-4367d5`) was deleted. A second attempt with
faithfulness only and a 900s cap completed both cases. No timed-out case is recorded
as a zero.

BigQuery rows:

```
ragas-20261127T031656Z-7364c9, pii_escalation,     faithfulness 0.6,    passed false
ragas-20261127T031656Z-7364c9, safety_authority,   faithfulness 0.6923, passed false
```

Both have `tool_trajectory_passed = true`; `passed` is false only because faithfulness
is below 0.70.

## Interpretation

- The trajectory defects are fixed: the agent no longer searches after a definitive
  missing or decommissioned record.
- The safety grounding improved substantially but is not solved. The remaining
  unsupported content is likely the general "confirm with the duty controller"
  guidance and the model's own framing, which the retrieved passage does not contain.
  The next tightening should make the refusal shorter: one source sentence, the
  hand-off, and nothing else.
- `pii_escalation` moved less; the answer still adds context around the refusal.

## Caveats

- Local agent and local retrieval; not the deployed Cloud Run path.
- Two cases only for the targeted RAGAS pass; no answer relevancy.
- The judge is probabilistic; a 0.6923 is not a stable threshold crossing.
- `agent_demo_data` disappears at the 28 November teardown. The captured dataset and
  this receipt remain; a future rerun should use a permanent `agent_eval_data`.
- The demo's five-day stack is still live; teardown is due on 28 November.

## Evidence

`raw/phase4-promptfix/` contains `captured.jsonl`, `trajectory.json`,
`adk-eval-promptfix.log`, `ragas-20261127T031656Z-7364c9.json`, `bq-rows.csv`.
