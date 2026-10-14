# Hospital Surgery Management AI Agent

An internal hospital operations assistant: a real, tool-using LangGraph agent
(backed by Gemini Flash) on top of a proper FastAPI + service/repository
backend, a RAG pipeline over synthetic hospital policy documents, and a
multipage Streamlit operations console.

> **All patient data and hospital policy documents in this repository are
> synthetic and fictional**, created for this portfolio project. Nothing here
> represents a real hospital, patient, or policy.

## 1. Project overview

Hospital scheduling staff need to check today's surgeries, spot delays, look
up policy, and schedule/reschedule/cancel surgeries -- today mostly done by
clicking through a scheduling system or asking a colleague. This project
builds an AI agent that can do all of that through natural language, backed by
a real operations API, with every write operation validated and confirmed
before it happens.

## 2. Business problem

See the full brief in-repo; in short, the system supports:

- Viewing today's surgeries and delayed surgeries
- Looking up a surgery's status
- Searching hospital policy (cancellation, scheduling, delay, OR, emergency,
  patient-prep) with page-level citations
- Scheduling, rescheduling, cancelling, and updating the status of surgeries
  (always with a confirm-before-execute step)
- Checking operating-room availability and surgeon schedules
- Viewing operational dashboard metrics
- Maintaining an immutable audit trail of every change

## 3. Key capabilities

- **12 agent tools** across reads, writes, RAG, and audit (full list below).
- **LangGraph `StateGraph`** agent with an explicit agent<->tools loop, bounded
  iterations, and a typed state object.
- **RAG over synthetic policy docs**: Hugging Face `sentence-transformers` +
  ChromaDB, page-aware citations, explicit insufficient-evidence handling.
- **Confirm-before-execute** workflow for every write operation.
- **Service/repository layered backend** with real business rules (OR/surgeon
  conflict detection, status-transition legality, cancellation eligibility).
- **Centralized error handling**, structured JSON logging with request IDs.
- **Prompt-injection defenses** tested against a fixture document.
- **102 automated tests** (pytest) across repositories, services, tools, RAG,
  agent routing, the API, and security -- see `docs/evaluation.md` for the
  honestly-reported coverage.

## 4. Architecture

See `docs/architecture.md` for the full diagram and reasoning. Summary:

```
Streamlit -> FastAPI -> LangGraph Agent -> Tools -> Services -> Repositories -> JSON data
                                              |
                                      RAG (policies/ -> ChromaDB)
```

## 5. Technology stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Agent | LangChain, LangGraph `StateGraph` |
| LLM | Gemini Flash (primary), optional Ollama (offline/dev fallback) |
| RAG | Hugging Face `sentence-transformers`, ChromaDB |
| Frontend | Streamlit |
| Testing | pytest, pytest-cov |
| Deployment | Docker, Docker Compose |
| Data | JSON files (synthetic structured data), text/PDF (synthetic policies) |

No Kafka, Kubernetes, Redis, Celery, Postgres, microservices, or Terraform --
deliberately, see `docs/architecture.md`.

## 6. Project structure

```
app/
  agent/        LangGraph state, graph, prompts, LLM provider abstraction
  api/v1/        FastAPI routers (surgeries, rooms, surgeons, dashboard, chat, policies)
  core/          exceptions, logging, security helpers
  models/        domain schemas + API request/response models
  rag/           loader, chunker, embeddings, vector store, retriever, ingest
  repositories/  JSON-file persistence
  services/      business rules
  tools/         the 12 agent-facing tools + registry
  config.py      environment-based settings
  dependencies.py dependency-injection container
  main.py        FastAPI app, middleware, exception handlers
data/            synthetic patients/surgeons/rooms/surgeries/events (JSON)
policies/        synthetic hospital policy documents (.txt)
frontend/        Streamlit multipage app
tests/           pytest suite
evaluation/      evaluation dataset + script
scripts/         data generation, policy ingestion CLIs
docs/            architecture, agent workflow, RAG, API, evaluation, security, interview guide
```

## 7. Setup

Requires Python 3.11+.

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY
```

## 8. Environment variables

See `.env.example` for the full list. The essentials:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `gemini` (default) or `ollama` |
| `GEMINI_API_KEY` | Required when `LLM_PROVIDER=gemini` |
| `GEMINI_MODEL` | Defaults to `gemini-2.5-flash` |
| `EMBEDDING_MODEL` | Defaults to `sentence-transformers/all-MiniLM-L6-v2` |
| `CHROMA_PERSIST_DIRECTORY` | Where the vector index is stored (`./chroma_data`) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | RAG chunking parameters (see `docs/rag.md`) |

**Optional Ollama fallback**: set `LLM_PROVIDER=ollama`, have
[Ollama](https://ollama.com) running locally with a tool-calling-capable model
(e.g. `ollama pull llama3.1`), and `pip install langchain-ollama` (not in the
default requirements, since Gemini is the primary/default path).

## 9. Running locally

Generate synthetic data (already included, but re-run any time to refresh
relative to "today"):

```bash
python scripts/generate_synthetic_data.py
```

Ingest hospital policies into ChromaDB (also runs automatically on first
backend startup if the vector store is empty):

```bash
python scripts/ingest_policies.py
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Start the frontend (in a separate terminal):

```bash
cd frontend
streamlit run streamlit_app.py
```

- API docs: http://localhost:8000/docs
- Frontend: http://localhost:8501

## 10. Running with Docker

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:8501

The backend container auto-ingests policy documents on first startup. Gemini
configuration comes from `.env` (not committed -- see `.env.example`).

## 11. API endpoints

See `docs/api.md` for the full reference, including the DELETE-vs-cancel
design decision. Summary: `/api/v1/surgeries*`, `/api/v1/operating-rooms*`,
`/api/v1/surgeons*`, `/api/v1/dashboard/summary`, `/api/v1/chat`,
`/api/v1/policies/*`, plus top-level `/health`.

## 12. Agent workflow

See `docs/agent-workflow.md`. Summary: `START -> agent -> (tools -> agent)* ->
END`, typed `AgentState`, and a confirm-then-execute contract for every write
tool.

## 13. Tool descriptions

| # | Tool | Purpose |
|---|---|---|
| 1 | `get_todays_surgeries` | List today's surgeries |
| 2 | `get_delayed_surgeries` | List currently delayed surgeries |
| 3 | `get_surgery_status` | Look up one surgery by ID |
| 4 | `search_hospital_policy` | RAG search over policy documents |
| 5 | `cancel_surgery` | Confirm-then-cancel a surgery |
| 6 | `create_surgery` | Confirm-then-schedule a new surgery |
| 7 | `reschedule_surgery` | Confirm-then-move a surgery |
| 8 | `update_surgery_status` | Confirm-then-transition status |
| 9 | `get_operating_room_availability` | Check OR availability in a window |
| 10 | `get_surgeon_schedule` | Get a surgeon's schedule |
| 11 | `get_surgery_dashboard` | Operational KPIs |
| 12 | `add_surgery_event` | Append a free-form audit note |

## 14. RAG pipeline

See `docs/rag.md` for the full pipeline and the reasoning behind the chunk
size/overlap defaults.

## 15. Business rules

See `docs/architecture.md` and `app/services/surgery_service.py`. Summary: OR
and surgeon double-booking are rejected, status transitions follow an explicit
allowed-transition map, completed surgeries can't be cancelled or rescheduled,
and every write creates an audit event.

## 16. Safety / guardrails

See `docs/security.md`: confirm-then-execute for writes, prompt-injection
defenses (tested against a fixture), secret redaction in logs, scope
limitation to operations (no clinical advice), and centralized error handling
with no leaked stack traces.

## 17. Testing

```bash
pytest
# with coverage:
pytest --cov=app --cov-report=term-missing
```

104 tests across repositories, services, tools, RAG, agent routing (via a
scripted fake LLM, no API key required), the API, and security. Current
coverage: **93%** (measured, not claimed as 100% -- see `docs/evaluation.md`
for the honest gaps, mainly the live-LLM-calling code paths).

The full write-confirmation workflow (`cancel_surgery`: propose -> confirm ->
execute) has also been manually verified end to end against the real Gemini
API, through both the raw API and the Streamlit chat UI -- this is what
surfaced and led to fixing a real bug in the chat history round-trip (see
`docs/agent-workflow.md`, "A real bug this caught").

## 18. Evaluation

```bash
python evaluation/eval_agent.py
```

See `docs/evaluation.md` for methodology and what this evaluation does and
does not prove.

## 19. Limitations

- Synthetic data/policies only; file-based JSON persistence (not a real
  database); no authentication/authorization; single-process deployment.
- The chat confirmation workflow relies on the LLM correctly interpreting
  user consent (see `docs/security.md`, Known limitations).
- See `docs/architecture.md` and `docs/interview-guide.md` for the full,
  honest limitations list and what would change for production use.

## 20. Production scaling considerations

See `docs/architecture.md` ("Production scaling considerations") and
`docs/interview-guide.md` for how this would evolve for 50-100 hospital
employees: PostgreSQL, SSO/RBAC, a managed vector service, load-balanced
replicas, background ingestion, a secret manager, and real observability.
