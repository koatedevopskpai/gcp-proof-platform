# Baseline: gpt-4o-mini (old model), 18 Nov 2026

Final reference run on the model OpenAI is retiring (snapshot `gpt-4o-mini-2024-07-18`, shutdown
14 Jan 2027, per OpenAI's deprecations page, read 18 Nov 2026). This is the "before" column for the
planned re-baseline on the replacement model.

- Command: `python scripts/repeat_runs.py --arm provider --runs 5 --model gpt-4o-mini`
- Code: branch `phase-2/fix-ai-judge-issue`, commit `3a35a7a` plus `scripts/repeat_runs.py`
  (history was rewritten on 18 Nov 2026 to remove a non-code file; commit ids here are post-rewrite)
- Temperature 0. 5 runs per dataset, 80 judge calls.
- Price basis: $0.15 input / $0.60 output per 1M tokens (checked 18 Nov 2026)
- Measured total cost: **$0.001025**

| Dataset | Scores across 5 runs | Median | Spread |
|---|---|---|---|
| eval_set | 0.9375 x5 | 0.9375 | 0 |
| control_verbatim | 1.0 x5 | 1.0 | 0 |
| control_verbatim_distracted | 1.0 x5 | 1.0 | 0 |
| control_unsupported | 0.4 x5 | 0.4 | 0 |
| control_unsupported_subtle | 0.65, 0.65, 0.65, 0.6, 0.4 | 0.65 | **0.25** |

Only the subtle case moves. In run 5 faithfulness flipped 0.5 -> 0.0 on identical input.

The lexical arm was also run 3x per dataset: identical every time (`raw/summary-lexical.json`).

Raw per-run reports are in `raw/` with `SHA256SUMS.txt` (42 files). Verify them from inside `raw/`, because the
paths in the checksum file are relative to it:

```bash
cd raw && sha256sum -c ../SHA256SUMS.txt
```
