# Architecture

SENTINEL-911 is a decision-support prototype. High-stakes actions stop at human approval.

## Pipeline

1. **Ingest** — transcript/audio hint, optional image, lat/lon/address  
2. **ASR / Vision / Geo providers** — real models if available, else demo  
3. **Entity fusion** — canonical Incident + conflicts + provenance  
4. **RAG** — BM25 + dense + RRF over DEMO protocols  
5. **Deterministic triage** — Python scoring only  
6. **Resource plan** — mock units/facilities/ETA  
7. **Safety validator** — deterministic rules  
8. **Explain** — features + DEMO citations + LLM narrative (non-authoritative)  
9. **Human approval** — Approve / Amend / Reject / Escalate  

## Providers

```
ASRProvider → WhisperASRProvider | DemoASRProvider
VisionProvider → YOLOVisionProvider | VLMVisionProvider | DemoVisionProvider
LLMProvider → OpenAIProvider | DemoLLMProvider
```

## Agent graph

`validate_intake → modality → fuse → retrieve_protocol → score_urgency → plan_resources → safety_validator → (revise_plan ≤2) → explain → human_approval | abstain`

No uncontrolled loops.
