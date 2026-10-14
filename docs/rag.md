# RAG Pipeline

## Corpus

Six synthetic policy documents live under `policies/` as plain text with an
explicit page-break convention (`--- PAGE N ---`), so citations can reference a
real page number even though the source isn't a real PDF:

- `surgery_cancellation_policy.txt`
- `surgery_scheduling_policy.txt`
- `surgery_delay_policy.txt`
- `operating_room_policy.txt`
- `emergency_surgery_policy.txt`
- `patient_preparation_policy.txt`

Every file is explicitly labelled `SYNTHETIC / SAMPLE HOSPITAL POLICY -- FOR
PORTFOLIO DEMONSTRATION ONLY` in its header. The loader also supports real
`.pdf` files via `pypdf` (native page numbers), so dropping a real PDF into
`policies/` and re-ingesting works without code changes.

## Pipeline stages (`app/rag/`)

1. **`loader.py`** -- reads every `.txt`/`.pdf` file in the policy directory
   and splits it into `DocumentPage(document_name, page_number, text)` records.
   For `.txt` files it parses the `--- PAGE N ---` markers; for `.pdf` files it
   uses each PDF page natively.
2. **`chunker.py`** -- splits each page's text into overlapping chunks
   (`CHUNK_SIZE=1000`, `CHUNK_OVERLAP=150` by default), preferring to break on
   a paragraph boundary, falling back to a sentence boundary, and only
   hard-cutting mid-sentence as a last resort. Each chunk also records the
   nearest preceding `SECTION N: ...` heading as its `section` metadata.
3. **`embeddings.py`** -- wraps `sentence-transformers/all-MiniLM-L6-v2` as a
   ChromaDB-compatible embedding function, loaded once per process.
4. **`vector_store.py`** -- a thin wrapper over a persistent ChromaDB
   collection (`chroma_data/`), storing `document_name`, `page_number`,
   `section`, and `chunk_id` as metadata alongside each chunk's text.
5. **`retriever.py`** -- queries the top-k most similar chunks, filters out
   anything below `MIN_RELEVANCE_SCORE` (0.30 cosine similarity), and builds
   both the citation strings and the `<untrusted_document>`-wrapped context
   that gets placed in the prompt.
6. **`ingest.py`** -- orchestrates steps 1-4 end to end; used by
   `scripts/ingest_policies.py` (CLI) and `POST /api/v1/policies/ingest` (API).

## Why these chunk-size/overlap values

- **1000 characters**: policy paragraphs in this corpus run roughly 400-900
  characters, so a 1000-character chunk usually captures one to two full
  paragraphs or a complete section point without truncating a rule
  mid-sentence. Larger chunks would dilute the embedding with less-relevant
  surrounding text; much smaller chunks would frequently split a single rule
  across two chunks.
- **150-character overlap (~15%)**: enough to carry a trailing sentence or a
  section heading into the next chunk, so a rule that falls near a boundary is
  still retrievable from either side, without the 2-3x storage/embedding cost
  a 50% overlap would add.

These are documented defaults, not tuned against a large labelled benchmark --
see `docs/evaluation.md` for the honest scope of evaluation performed.

## Page-aware citations

Every retrieved chunk carries `document_name` and `page_number` (and `section`
when available), formatted as, e.g.:

```
[surgery_cancellation_policy.txt - Page 4] (SECTION 7: EXAMPLES)
```

The agent is instructed to include these citations whenever it answers a
policy question.

## Insufficient evidence handling

`PolicyRetriever.retrieve()` returns `sufficient_evidence: False` whenever no
retrieved chunk clears `MIN_RELEVANCE_SCORE`. The `search_hospital_policy` tool
turns this into an explicit instruction to the LLM: *"No hospital policy
documents provided sufficiently relevant evidence... state that the policy
corpus does not cover this"* rather than letting the model guess from general
knowledge. This is covered by `tests/test_rag.py` (off-topic query) and
`tests/test_tools.py`.

## Treating retrieved content as untrusted

Every chunk is wrapped (`app/core/security.py::wrap_untrusted_content`) in an
explicit `<untrusted_document source="...">...</untrusted_document>` block
with a trailing note that the content is data to cite, never instructions to
follow. This is the mechanism tested in `tests/test_security.py` against a
fixture document that contains an embedded prompt-injection attempt.
