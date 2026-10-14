# Architecture

## Layered design

```
Hospital Staff
     |
     v
Streamlit Frontend (frontend/)
     |  HTTP (requests)
     v
FastAPI API (app/api/v1/*)
     |
     v
LangGraph Agent (app/agent/*)         <-- only entry point that an LLM touches
     |
     v
Tool Layer (app/tools/*)              <-- translates agent intent into service calls
     |
     v
Service Layer (app/services/*)        <-- business rules, conflict checks, transitions
     |
     v
Repository Layer (app/repositories/*) <-- JSON file persistence
     |
     v
data/*.json (synthetic hospital data)
```

A parallel path handles policy documents:

```
policies/*.txt
     |
     v
Loader (app/rag/loader.py)        -- splits into pages, preserves page numbers
     |
     v
Chunker (app/rag/chunker.py)      -- paragraph-aware chunks with section metadata
     |
     v
Embeddings (app/rag/embeddings.py) -- sentence-transformers (Hugging Face)
     |
     v
ChromaDB (app/rag/vector_store.py) -- persistent vector store
     |
     v
Retriever (app/rag/retriever.py)  -- top-k query + insufficient-evidence check
     |
     v
search_hospital_policy tool -> LangGraph agent -> grounded response + citations
```

## Why this separation

Each layer has exactly one responsibility, which is what makes the system testable
and defensible in an interview:

- **Repositories** only read/write JSON files. They know nothing about business
  rules (e.g. they will happily store a surgery with any status) and nothing
  about the agent.
- **Services** own every business rule: scheduling conflicts, status-transition
  legality, cancellation eligibility. They are plain Python classes with no
  FastAPI or LangChain imports, so they're trivial to unit test (see
  `tests/test_services.py`) and could be reused by a future batch job or CLI.
- **Tools** (`app/tools/*.py`) are the only code the LLM can "call". They are
  thin: validate via the service, return a JSON-serializable dict, never touch
  a repository directly. Every write tool (`cancel_surgery`, `create_surgery`,
  `reschedule_surgery`, `update_surgery_status`) implements the same
  confirm-then-execute contract (see `docs/agent-workflow.md`).
- **The agent** (`app/agent/graph.py`) only decides *which* tool to call and
  *what arguments* to pass. It cannot mutate data by any other path -- there is
  no "raw SQL" or "write to JSON" escape hatch available to the LLM.
- **The API** is a second, independent consumer of the service layer. The
  direct REST endpoints (`PATCH /surgeries/{id}/status`, etc.) do not go
  through the agent's confirmation workflow -- they are the "I am a human
  calling an API and I already decided" path, same as any REST API. The
  two-step confirmation is specifically a safeguard against an LLM
  autonomously executing a destructive action from ambiguous natural language.

## Why file-based JSON instead of a database

This is a portfolio-scale implementation. A real hospital system would use
PostgreSQL (or similar) with proper transactions, concurrent-write safety, and
backup/restore. Here:

- Each repository is a single JSON array file, read/written under a
  per-repository `threading.Lock` to prevent corruption from concurrent FastAPI
  requests in a single process.
- This keeps the "data layer" fully inspectable (open `data/surgeries.json` in
  a text editor) and removes any external dependency (no DB container, no
  connection string) -- appropriate for a project meant to be cloned and run
  in minutes.
- The repository interface (`list_all`, `get_by_id`, `create`, `update`,
  `delete`, `append`) is deliberately the same shape a SQLAlchemy repository
  would expose, so swapping the implementation for Postgres would not require
  touching the service layer.

## Technology choices and why

| Concern | Choice | Why |
|---|---|---|
| Agent orchestration | LangGraph `StateGraph` | Explicit state machine (agent <-> tools loop) is easier to reason about and test than an implicit agent loop; the typed `AgentState` makes the confirmation workflow visible in the state itself. |
| LLM | Gemini Flash (`langchain-google-genai`) | Fast, cheap, good tool-calling support; configurable via env vars so swapping models/providers needs no code change. |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Small (~80MB), runs locally/offline, fast enough for a demo corpus, good semantic quality for short policy paragraphs. |
| Vector store | ChromaDB (persistent client) | Zero-infrastructure embedded vector DB; trivial to run locally or in a single Docker container; swappable for a managed vector service in production (see below). |
| API | FastAPI + Pydantic | Typed request/response models, automatic OpenAPI docs, async-friendly, industry-standard for Python services. |
| Frontend | Streamlit | Fast to build a real internal-tool-feeling multipage app without a separate JS build pipeline. |

## Production scaling considerations

This project is explicitly **not** production-ready for a real hospital. If this
were to grow to support 50-100 hospital employees in production, the following
would change (see also `docs/interview-guide.md`):

- **Persistence**: JSON files -> PostgreSQL, with the repository layer's
  interface unchanged so services/tools/API need no changes.
- **Vector store**: local Chroma -> a managed vector/search service (e.g.
  a hosted Chroma/pgvector/OpenSearch), with ingestion moved to a background
  job/queue so large policy updates don't block a request.
- **Auth**: no authentication today (any caller can hit the API) -> SSO /
  Azure Entra ID with RBAC so only authorized scheduling staff can perform
  write operations, and the `actor` field in audit events becomes a verified
  identity instead of a free-text field.
- **Secrets**: `.env` file -> a managed secret store (e.g. Key Vault).
- **Scaling**: single-process Uvicorn -> multiple load-balanced FastAPI
  replicas behind a reverse proxy; the JSON file locks would need to become a
  real database's transactional guarantees at that point.
- **Observability**: structured stdout logs -> centralized log aggregation and
  metrics/alerting (e.g. on delay rates, tool error rates, LLM latency).
- **Compliance**: real patient data would require HIPAA-equivalent controls
  (encryption at rest, access logging, data retention policy) well beyond this
  portfolio's synthetic-data scope.
