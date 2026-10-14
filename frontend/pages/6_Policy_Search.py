import streamlit as st
from utils.api_client import api_call, post

st.set_page_config(page_title="Policy Search - Hospital Surgery AI", page_icon="📄", layout="wide")
st.title("📄 Hospital Policy Search")
st.caption(
    "Retrieval-augmented search over the hospital's synthetic policy documents. "
    "Answers are grounded in retrieved text with page-level citations; if nothing "
    "relevant is found, the system says so instead of guessing."
)

query = st.text_input("Ask a policy question", placeholder="e.g. Can an in-progress surgery be cancelled?")
if st.button("Search") and query:
    result, err = api_call(post, "/api/v1/policies/search", json={"query": query})
    if err:
        st.error(err)
    elif not result["sufficient_evidence"]:
        st.warning("No policy documents provided sufficiently relevant evidence for this question.")
    else:
        st.success("Relevant policy text found:")
        st.text_area("Retrieved context (shown as sent to the LLM)", result["context"], height=300)
        st.caption("Citations: " + " · ".join(result["citations"]))

with st.expander("Re-ingest policy documents (rebuild the vector index)"):
    st.caption("Use this after editing files under policies/.")
    if st.button("Run ingestion"):
        result, err = api_call(post, "/api/v1/policies/ingest")
        if err:
            st.error(err)
        else:
            st.success(f"Ingested {len(result['documents_ingested'])} documents, {result['chunk_count']} chunks.")
