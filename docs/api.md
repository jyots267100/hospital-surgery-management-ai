# API Reference

Base path: `/api/v1`. Interactive OpenAPI docs are available at `/docs` (Swagger)
and `/redoc` once the server is running.

## Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check. Not under `/api/v1` so load balancers/orchestrators can probe it without API versioning concerns. |

## Surgeries

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/surgeries` | List surgeries. Query params: `status` (filter by `SurgeryStatus`), `today_only` (bool). |
| GET | `/api/v1/surgeries/delayed` | List surgeries currently marked `delayed`. |
| GET | `/api/v1/surgeries/{surgery_id}` | Get one surgery. 404 if not found. |
| POST | `/api/v1/surgeries` | Create a surgery. Validates patient/surgeon/room existence and OR/surgeon conflicts; 409 on conflict, 404 on unknown reference, 422 on invalid input. |
| PATCH | `/api/v1/surgeries/{surgery_id}/status` | Change status (`scheduled`\|`confirmed`\|`in_progress`\|`completed`\|`delayed`\|`cancelled`), with optional `reason`/`delay_minutes`. Invalid transitions return 409. |
| PATCH | `/api/v1/surgeries/{surgery_id}/reschedule` | Move to a new date/time/room. Conflicts return 409. |
| POST | `/api/v1/surgeries/{surgery_id}/events` | Append a free-form audit event (e.g. a note). |
| GET | `/api/v1/surgeries/{surgery_id}/events` | Get the full, immutable audit history for a surgery. |
| DELETE | `/api/v1/surgeries/{surgery_id}` | **Administrative hard-delete only** -- see design decision below. |

### Design decision: DELETE is not cancellation

`DELETE /api/v1/surgeries/{surgery_id}` permanently removes the record. This is
**intentionally not** how a surgery is cancelled in normal operation, for two
reasons documented in `policies/surgery_cancellation_policy.txt` (Section 6):

1. A cancelled surgery must remain visible for audit/reporting purposes --
   deleting it would destroy that trail.
2. The agent's `cancel_surgery` tool and the direct API path both represent
   cancellation as a **status transition**:

   ```
   PATCH /api/v1/surgeries/{surgery_id}/status
   { "status": "cancelled", "reason": "..." }
   ```

`DELETE` exists only so an operator can remove a synthetic/test record created
by mistake during a demo; it is never called by the agent and the Streamlit UI
does not expose it as the "Cancel" action.

## Operating rooms

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/operating-rooms` | List all rooms. |
| GET | `/api/v1/operating-rooms/{room_id}` | Get one room. |
| GET | `/api/v1/operating-rooms/{room_id}/availability?on_date=&window_start=&window_end=` | Check availability in a time window; returns any conflicting surgeries. |

## Surgeons

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/surgeons` | List all surgeons. |
| GET | `/api/v1/surgeons/{surgeon_id}` | Get one surgeon. |
| GET | `/api/v1/surgeons/{surgeon_id}/schedule?on_date=` | Get a surgeon's schedule, optionally filtered to a date. |

## Dashboard

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/dashboard/summary` | Status counts, average delay, OR utilization. |

## Agent

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/chat` | One conversational turn. Body: `{"message", "history": [{"role","content"}], "actor"}`. Response includes `response`, `citations`, `pending_action`, `confirmation_status`, and the updated `history` to pass back on the next turn. |

## Policy

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/policies/search` | Direct RAG search (used by the Streamlit Policy Search page and the evaluation script), bypassing the LLM. |
| POST | `/api/v1/policies/ingest` | Re-run ingestion (load -> chunk -> embed -> store) after editing files under `policies/`. |

## Error format

All domain errors share one JSON shape, produced by a centralized exception
handler (`app/main.py`) so no stack trace is ever returned to a client:

```json
{
  "error": "ConflictError",
  "detail": "Operating room OR-2 is already booked for surgery S1010 at 10:00:00",
  "context": {"conflicting_surgery_id": "S1010"}
}
```

| Exception | HTTP status |
|---|---|
| `NotFoundError` | 404 |
| `ValidationError` | 422 |
| `ConflictError` | 409 |
| `InvalidStateTransitionError` | 409 |
| `PolicyViolationError` | 422 |
| `ConfirmationRequiredError` | 409 |
| `RepositoryError` | 500 |
| `RAGError` | 502 |
| `LLMError` | 502 |
| Anything unhandled | 500, generic message, no stack trace |
