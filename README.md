# SENTINEL-911

**Autonomous Multi-Modal Emergency Dispatch & Triage Co-Pilot**  
*(Research / educational decision-support prototype)*

> **⚠ NOT FOR REAL EMERGENCY DISPATCH**  
> SENTINEL-911 is a portfolio / research demo. It does **not** contact emergency services, does **not** auto-dispatch units, and is **not** clinically validated.  
> **AI recommends. Human decides.**

---

## Problem

Emergency call-taking is multimodal: callers speak under stress, photos may arrive from the scene, and location metadata is noisy. Modalities can disagree (e.g. “small kitchen fire” vs structural fire on camera). Pure LLM scoring is unsafe for urgency. Dispatchers also face duplicate callers for the same incident.

## Solution

SENTINEL-911 fuses audio, vision, and location into a canonical **Incident Object**, retrieves **DEMO protocol** excerpts with citations, scores urgency with a **deterministic** engine (LLM never assigns the score), plans mock resources, validates safety rules, explains the decision, and stops at **human approval**.

```
INPUT → Audio / Vision / Location (parallel)
      → Entity Fusion (+ modality conflicts)
      → RAG Protocol Retrieval (citations)
      → Deterministic Urgency Score
      → Resource Planning (mock)
      → Safety Validator
      → Explanation
      → Human Approval (Approve / Amend / Reject / Escalate)
      → Dispatcher Dashboard
```

## Features

- Multimodal ingestion with demo fallbacks (no GPU / API keys required)
- Canonical Pydantic Incident Object with hazard provenance
- Modality conflict detection (max-severity retained, shown in UI)
- Deterministic triage (weights + inspectable overrides)
- Hybrid RAG: BM25 + dense + Reciprocal Rank Fusion + DEMO citations
- Incident deduplication / clustering
- LangGraph-style explicit state machine (max 2 plan revisions)
- Safety validator + audit log
- Streamlit operations dashboard + Plotly map
- Live simulation + “Generate 10 Duplicate Calls” MCI demo
- FastAPI + WebSocket + SQLite + pytest + evaluation script

## Tech stack

| Layer | Tech |
|--------|------|
| API | FastAPI, Uvicorn, WebSockets, Pydantic |
| AI/ML | Provider abstractions (Whisper/YOLO/LLM optional); demo mode default |
| RAG | ChromaDB (optional), BM25, hashing/sentence embeddings, RRF |
| Agent | Explicit state machine (LangGraph-compatible stages) |
| UI | Streamlit, Plotly |
| DB | SQLite (SQLAlchemy) |
| Tests | pytest |

## Quick start (one demo path)

```bash
# From repo root
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

python scripts/generate_demo_data.py
python scripts/ingest_protocols.py

# Terminal 1 — API
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — Dashboard
streamlit run frontend/app.py
```

Open the Streamlit app → click **▶ RUN EMERGENCY SIMULATION**.

Optional Docker:

```bash
docker compose up --build
```

- API: http://127.0.0.1:8000/docs  
- Dashboard: http://127.0.0.1:8501  

## Environment variables

See `.env.example`:

| Variable | Default | Meaning |
|----------|---------|---------|
| `MODEL_MODE` | `demo` | `demo` / `hybrid` / `full` |
| `OPENAI_API_KEY` | empty | Optional LLM/VLM |
| `DATABASE_URL` | sqlite under `./data` | Persistence |
| `CHROMA_PATH` | `./data/chroma` | Vector store |
| `PROTOCOLS_PATH` | `./data/protocols` | Knowledge base |
| `LOG_RAW_AUDIO` | `false` | Privacy |

Demo mode works with empty API keys and no GPU.

## How triage scoring works

The LLM **never** sets urgency. Features are extracted; `backend/triage/engine.py` computes:

```
score = 0.40*life_threat + 0.25*casualty_load + 0.20*hazard_risk
      + 0.10*access + 0.05*caller_state
```

Clamped to 0–100. Tiers: RED ≥75, YELLOW ≥50, GREEN otherwise (BLACK for expectant).  
Overrides (inspectable): e.g. non-ambulatory → min 90; HAZMAT → min 85.

## How multimodal fusion works

Audio, vision, and location are fused in `backend/pipeline/fusion.py`. Disagreements create `ModalityConflict` entries. Safety-oriented scoring keeps the **higher-severity** signal and shows **⚠ MODALITY CONFLICT** in the dashboard.

## How RAG works

Synthetic DEMO protocol `.md` files under `data/protocols/` are chunked, retrieved with BM25 + dense embeddings, fused via RRF, and cited as `[DEMO_PROTOCOL §…]`. They are **not** official government protocols. Low confidence → *“Insufficient protocol evidence — human review required.”*

Add your own files to `data/protocols/` and run `python scripts/ingest_protocols.py`.

## How duplicate detection works

Same area + within ~10 minutes + high narrative similarity → shared `cluster_id` and caller count. MCI simulation generates many near-duplicate callers.

## Safety architecture

- No automatic dispatch / no real SMS / no real 911 calls  
- GREEN cannot receive highest-priority unit sets  
- HAZMAT needs warning + protocol citations  
- Low confidence and conflicts force human review  
- Approve / Amend / Reject / Escalate only update the audit log  

## Project structure

```
sentinel-911/
├── backend/          # FastAPI, pipeline, triage, RAG, agent, safety
├── frontend/app.py   # Streamlit dashboard
├── data/protocols/   # DEMO knowledge base
├── data/facilities/  # Mock units & facilities
├── scripts/          # demo data, ingest, evaluate
├── tests/            # pytest (≥15 tests)
├── docs/             # architecture, API, evaluation, safety
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

## Tests

```bash
pytest -q
```

## Evaluation

```bash
python scripts/evaluate.py
```

Reports only metrics supported by the demo labels; unsupported metrics are marked **Not evaluated** (no fabricated benchmarks).

## Example demo output

Vehicle crash simulation typically yields:

- Urgency ~90 **RED** (non-ambulatory override)  
- Fuel-leak + down casualty rules triggered  
- DEMO protocol citations  
- Mock ALS/engine recommendations  
- Status `pending_review` until a human clicks Approve  

## Research contribution (portfolio framing)

1. Multimodal fusion with **explicit conflict objects** (not silent averaging)  
2. **Deterministic** urgency with inspectable rules (LLM feature extraction only)  
3. Citation-forced protocol RAG over clearly labeled DEMO corpora  
4. Dedup clustering for multi-caller events  
5. Controlled agent graph with revision cap + abstain/escalate  

## Limitations

- Demo / synthetic protocols only  
- Vision/ASR use heuristics or optional models when available  
- Not validated for operational EMS use  
- Map uses demo coordinates  

## Future improvements

- Real Whisper / YOLOv8 / VLM backends behind existing providers  
- Agency SOP ingestion (with permission)  
- Stronger privacy (encryption, retention policies)  
- Offline evaluation sets with gold labels  

## Screenshots

_Add dashboard screenshots here for your GitHub README:_

1. Active incident queue (RED/YELLOW/GREEN)  
2. Incident detail with conflict banner + feature bars  
3. Map + MCI duplicate cluster  

## License / ethics

Educational use only. Production emergency systems require legal, privacy, security, and agency validation beyond this prototype.

---

**SENTINEL-911** — *AI recommends, human decides.*
