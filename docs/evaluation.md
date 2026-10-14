# Evaluation

## Methodology

`evaluation/eval_agent.py` runs `evaluation/eval_dataset.json` (15 hand-written
cases) against the real system and reports pass/fail/skip honestly -- it does
not fabricate a score.

Two evaluation paths, because they need different things to run:

1. **RAG grounding / hallucination resistance** (`rag_grounding`,
   `hallucination_resistance` categories) call `PolicyService.search()`
   directly -- no LLM required. These check:
   - Does a clearly on-topic query (e.g. "Can a completed surgery be
     cancelled?") return `sufficient_evidence=true` with a citation from the
     expected document?
   - Does a clearly off-topic or unanswerable query (e.g. "What's the weather
     forecast for tomorrow?") correctly return `sufficient_evidence=false`
     rather than a hallucinated answer?

2. **Tool selection / argument correctness / state-change safety**
   (`tool_selection`, `state_change_safety` categories) run one real turn
   through the compiled LangGraph agent with the configured Gemini model and
   inspect the first tool call the model made: is it the expected tool, and do
   its arguments contain the expected key/value pairs (a subset match, since
   the model may pass additional reasonable arguments)? For write tools, the
   case also checks `confirmed=false` on the first call.

   **These require `GEMINI_API_KEY` to be set.** If the LLM call fails (e.g.
   no key configured), the case is reported as `SKIP` with the underlying
   error message -- never silently passed or given a fabricated score.

## Running it

```bash
python evaluation/eval_agent.py
```

Output is printed to stdout and written to `evaluation/results/latest_results.json`
(git-ignored, since it depends on live model behavior and is not meant to be a
committed "proof" artifact).

## What this evaluation does and does not prove

- It **does** give a repeatable, inspectable signal that the six seeded policy
  documents are chunked/embedded/retrieved sensibly, and that common phrasings
  of the 12 supported operations route to the correct tool with sane
  arguments.
- It **does not** constitute a statistically rigorous benchmark -- 15 cases is
  enough to catch obvious regressions (e.g. a prompt change that breaks tool
  routing, or a chunking change that breaks retrieval for a known query), not
  enough to claim a precise accuracy percentage. Any number this script
  prints should be read as "N of 15 hand-picked cases," not "X% accuracy."
- Citation correctness is checked at the document level (did the citation
  reference the expected policy file), not at the exact-page level, since
  policy text spans pages and more than one page can legitimately be relevant.
- This script intentionally does not attempt to score free-text answer
  *quality* (e.g. via an LLM-as-judge) -- doing that well requires its own
  calibration effort that would be dishonest to present as "done" within this
  portfolio's scope. A natural next step would be adding an LLM-judge rubric
  for answer groundedness, with its own validation against human-labeled
  examples.

## Test suite vs. evaluation script

`tests/` (pytest) checks deterministic, mocked-LLM behavior -- repository CRUD,
service business rules, tool contracts, RAG chunking/retrieval mechanics, and
agent graph routing against a scripted fake model (`tests/fakes.py`). It is
fast, has no external dependency, and runs in CI.

`evaluation/eval_agent.py` additionally checks real-model behavior against
Gemini. It is slower, costs API calls, and is run on demand -- it is evaluation,
not a CI gate.
