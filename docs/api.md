# API Overview

Base URL: `http://127.0.0.1:8000`  
Interactive docs: `/docs`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Status + component modes + disclaimer |
| GET | `/scenarios` | Demo scenario list |
| POST | `/incidents` | Create + analyze incident |
| GET | `/incidents` | List incidents (urgency sorted) |
| GET | `/incidents/{id}` | Detail |
| POST | `/incidents/{id}/analyze` | Re-run analysis |
| POST | `/incidents/{id}/approve` | Human approve (audit only) |
| POST | `/incidents/{id}/amend` | Human amend |
| POST | `/incidents/{id}/reject` | Human reject |
| POST | `/incidents/{id}/escalate` | Human escalate |
| POST | `/simulation/run` | Run scenario pipeline |
| POST | `/simulation/mci` | Multi-caller duplicate demo |
| GET | `/clusters` | Duplicate clusters |
| GET | `/protocols/search?q=` | DEMO protocol search |
| GET | `/metrics` | Queue metrics |
| GET | `/audit` | Audit log |
| WS | `/ws/incidents` | Live snapshot stream |

All responses include a research/demo disclaimer. Approve/Amend/Reject/Escalate **never** contact real emergency services.
