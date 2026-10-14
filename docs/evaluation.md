# Evaluation

Run:

```bash
python scripts/evaluate.py
```

## Metrics policy

Do **not** fabricate results. The script reports:

- Soft triage tier accuracy on demo scenarios  
- Cohen’s kappa when label diversity allows  
- RAG retrieval hit rate / citation coverage on demo queries  
- Latency p50/p95 for the demo pipeline  
- Dedup cluster precision proxy on MCI simulation  

Unsupported metrics (entity F1, faithfulness, etc.) are reported as **Not evaluated**.

Latest machine-written report (if present): `docs/evaluation_last_run.json`.
