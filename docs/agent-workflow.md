# Agent Workflow

## State graph

The agent is a `langgraph.graph.StateGraph` with two nodes (`app/agent/graph.py`):

```
START -> agent
          |
          |-- AIMessage has tool_calls AND iteration_count < 6 --> tools -> agent (loop)
          |-- otherwise (no tool_calls, or iteration limit reached)       --> END
```

- **`agent` node**: prepends the system prompt (`app/agent/prompts.py`) if not
  already present, invokes the Gemini (or Ollama) chat model with tools bound
  via `bind_tools()`, and appends the resulting `AIMessage` to `messages`. LLM
  calls are wrapped in a bounded retry (`tenacity`, max 3 attempts, exponential
  backoff) that only retries clearly transient errors (timeout/rate-limit/5xx)
  -- it does not retry indefinitely and does not retry on e.g. an auth error.
- **`tools` node**: executes every tool call in the latest `AIMessage`,
  catching `DomainError` subclasses and unexpected exceptions so a single
  failed tool call becomes a structured error message back to the LLM instead
  of crashing the request. It also inspects tool results to populate
  `pending_action`, `confirmation_required`, `confirmation_status`, and
  `retrieved_context` in the shared state, so the API can surface "this needs
  your confirmation" without re-parsing the conversation.
- **Routing**: `route_after_agent` sends the graph back to `tools` only while
  the model keeps requesting tool calls and the iteration budget allows it;
  otherwise it ends, using the last `AIMessage.content` as `final_response`.

## Typed state

`app/agent/state.py` defines `AgentState` with the fields the spec asked for:
`messages` (full history), `user_query`, `selected_tool`, `tool_arguments`,
`tool_result`, `retrieved_context`, `pending_action`, `confirmation_required`,
`confirmation_status`, `final_response`, `error`, and `iteration_count` (loop
guard). `messages` uses LangGraph's `add_messages` reducer so each graph
invocation appends to history rather than overwriting it -- this is what lets a
confirmation flow span two separate HTTP requests (two chat turns) while still
being "the same conversation" from the LLM's point of view.

### A real bug this caught: history round-tripping must preserve tool calls

The `/api/v1/chat` endpoint is stateless -- there is no server-side session, so
the client (Streamlit, or any API caller) sends the prior conversation back as
`history` on every request, and the agent reconstructs LangChain messages from
it (`app/agent/service.py`). The first version of that reconstruction only
kept `{role, content}` per turn -- plain text. That passed every test written
against a scripted fake model (`tests/fakes.py`), because the fake model
doesn't actually look at its input to decide what to do next.

It failed against the real Gemini API: after proposing a cancellation
(`cancel_surgery(confirmed=false)`), a follow-up "yes, go ahead" sometimes made
the model respond with a repeated clarifying question instead of calling
`cancel_surgery(confirmed=true)` again -- because, from the reconstructed
history, the model had no structured record that it had ever called a tool at
all; it only saw its own prior sentence as plain text. The fix: `history` now
round-trips full `AIMessage.tool_calls` and `ToolMessage` content, not just
text (`_messages_to_history` / `_history_to_messages` in
`app/agent/service.py`), and `tests/test_agent.py` locks in both the
serialization fidelity and the full two-call flow. This is precisely why the
test suite's scripted-fake-model tests are necessary-but-not-sufficient --
the real-model smoke test against Gemini is what surfaced this gap.

### Three more bugs found live-testing the other write flows

With the history fix in place, all four write flows (`cancel_surgery`,
`create_surgery`, `reschedule_surgery`, `update_surgery_status`) were
exercised end to end against a real model (Gemini, and a local Ollama model
once the Gemini free-tier daily quota was exhausted mid-session -- both use
the identical graph/tool code path, so the findings apply equally). That
surfaced three more real, fixed bugs, none of which any scripted-fake-model
test could have caught, because each is specifically about how a *real*
model behaves, not about the graph's control flow:

1. **No current-date anchor.** Asked to schedule a surgery "tomorrow," the
   model resolved "tomorrow" from its training data rather than the real
   current date, producing a plausible-looking but wrong `scheduled_date`
   (e.g. a date from 2024). The confirmation workflow caught it before
   anything was written, but the *proposal itself* was wrong -- easy to miss
   if a user didn't check the date closely. Fixed by
   `app/agent/prompts.py::render_system_prompt()`, which appends the real
   current date (and weekday) to the system prompt on every turn, recomputed
   live rather than baked into a static string.
2. **Explicit `null` for defaulted tool arguments.** A local model emitted
   `{"duration_minutes": null, "priority": null, "confirmed": null}` instead
   of omitting those keys. Pydantic only applies a field's default when a key
   is *absent*; an explicit `null` for an `int`/`bool`/`str` field still fails
   validation, so the tool call raised and the request had to be retried.
   Fixed with a reusable `field_validator` (`app/tools/schema.py::
   _none_becomes_default`) that treats an explicit null the same as omitted
   for every optional/defaulted argument across all four write-tool schemas.
3. **Mixed timezone-naive/aware timestamps crashed audit history.** The
   synthetic data generator wrote naive timestamps while `EventService.
   add_event` always writes `datetime.now(timezone.utc)` (aware); sorting a
   surgery's events mixed both and Python raises on comparing a naive and an
   aware datetime -- so `GET /surgeries/{id}/events` 500'd for *any* seeded
   surgery that was ever written to live (i.e. almost any real usage).
   Fixed at both ends: the generator now writes aware timestamps
   (`scripts/generate_synthetic_data.py`), and `EventRepository.
   find_by_surgery` normalizes a naive timestamp to UTC before comparing
   (`app/repositories/event_repository.py::_sortable_timestamp`) so the sort
   can never crash regardless of where a timestamp originated.

All three have regression tests (`tests/test_agent.py`,
`tests/test_tools.py`, `tests/test_repositories.py`) that reproduce the exact
failure shape without needing a live model or API key.

## The confirmation workflow, concretely

Every write tool (`cancel_surgery`, `create_surgery`, `reschedule_surgery`,
`update_surgery_status`) takes a `confirmed: bool = False` argument and
validates the request (existence, conflicts, eligibility, legal status
transition) **regardless of `confirmed`**. The difference:

- `confirmed=False` (the default): the tool returns
  `{"status": "confirmation_required", ...proposal...}` and does **not**
  write anything.
- `confirmed=True`: the tool performs the mutation and returns
  `{"status": "executed", ...}`.

The system prompt instructs the LLM: always call a write tool with
`confirmed=false` first, present the proposal to the user in plain language,
and only call it again with `confirmed=true` once the user's next message is
clearly affirmative. Concretely, for cancellation:

```
User:      "Cancel surgery S1005."
Agent:     calls cancel_surgery(surgery_id="S1005", reason=..., confirmed=false)
Tool:      {"status": "confirmation_required", "message": "S1005 is scheduled for
            14:00 and is eligible for cancellation. Do you want me to proceed?"}
Agent:     "S1005 is scheduled for 14:00 and is eligible for cancellation under
            the current policy. Do you want me to cancel it?"
User:      "Yes, cancel it."
Agent:     calls cancel_surgery(surgery_id="S1005", reason=..., confirmed=true)
Tool:      executes the cancellation, creates an audit event, returns the
            updated surgery.
Agent:     "Surgery S1005 has been cancelled."
```

### A known limitation, stated honestly

The *gate* that prevents premature execution is enforced in two independent
places: the tool itself always validates first, and the system prompt
instructs the LLM on the two-step protocol. What is **not** independently
verified by the graph is "did the user's last message actually mean yes" --
that judgment call is made by the LLM. This is a reasonable trade-off for a
portfolio system (and is mitigated by low `temperature` and explicit prompt
wording), but a production system handling real patient scheduling would want
an additional deterministic confirmation step (e.g. a UI checkbox/button, not
just free-text parsing) before `confirmed=true` is ever set by anything other
than a human-driven UI control. The Streamlit "Surgery Management" page
implements exactly that: a UI-level review step before any write API call,
independent of the chat agent.

## Why the LLM never touches data directly

There is no tool that takes raw JSON or a file path. Every tool signature is a
small, typed Pydantic model (`app/tools/schema.py`); the tool function
translates validated arguments into a `SurgeryService` method call. The LLM
cannot, for example, ask to "set status to X" for an arbitrary surgery outside
the `ALLOWED_STATUS_TRANSITIONS` map in `app/models/schemas.py` -- the service
raises `InvalidStateTransitionError`, which becomes a structured error message
the LLM sees and must explain to the user, not a silent bypass.
