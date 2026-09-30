"""RAG-backed MCP tools: search_policy_documents, get_policy_section, check_policy_compliance."""
from __future__ import annotations

from app.config import RETRIEVAL_TOP_K
from app.rag import vector_store
from app.rag.retriever import retrieve
from mcp_server import data_access


def search_policy_documents(query: str, top_k: int = RETRIEVAL_TOP_K, doc_id: str | None = None) -> dict:
    """Search the CPDA policy corpus and return the top matching chunks with citations."""
    results = retrieve(query, top_k=top_k, doc_id_filter=doc_id)
    if not results:
        return {
            "query": query,
            "results": [],
            "note": "No matching policy content found in the corpus for this query.",
        }
    return {
        "query": query,
        "results": [
            {
                "doc_id": r.doc_id,
                "doc_title": r.doc_title,
                "section": r.section,
                "source_file": r.source_file,
                "snippet": r.snippet,
                "score": r.combined_score,
            }
            for r in results
        ],
    }


def get_policy_section(doc_id: str, section: str | None = None) -> dict:
    """Fetch the full text of a specific policy document, optionally filtered to one section."""
    raw = vector_store.get_by_doc(doc_id)
    ids = raw.get("ids", [])
    docs = raw.get("documents", [])
    metas = raw.get("metadatas", [])

    if not ids:
        return {"doc_id": doc_id, "found": False, "note": "No document found with this doc_id."}

    items = sorted(zip(ids, docs, metas), key=lambda x: x[0])
    sections: list[dict] = []
    for chunk_id, text, meta in items:
        sec_name = meta.get("section", "")
        if section and section.lower() not in sec_name.lower():
            continue
        sections.append({"section": sec_name, "text": text, "source_file": meta.get("source_file")})

    if not sections:
        return {
            "doc_id": doc_id,
            "found": False,
            "note": f"Document found but no section matched filter '{section}'.",
        }

    doc_title = items[0][2].get("doc_title", doc_id)
    return {"doc_id": doc_id, "doc_title": doc_title, "found": True, "sections": sections}


def check_policy_compliance(topic: str, employee_id: str | None = None, context: str | None = None) -> dict:
    """Gather policy evidence and (if given) employee context relevant to a compliance question.

    This tool does not itself issue a yes/no ruling -- it returns the retrieved policy evidence
    and the employee's relevant profile fields so the agent can produce a cited, grounded answer
    that distinguishes policy facts from recommendations, per the RAG guardrail requirements.
    """
    search_query = f"{topic} {context or ''}".strip()
    results = retrieve(search_query, top_k=6)

    employee_context = None
    if employee_id:
        emp = data_access.get_employee(employee_id)
        if emp is None:
            return {
                "topic": topic,
                "error": "employee_not_found",
                "message": f"No employee found with ID '{employee_id}'.",
            }
        employee_context = {
            "employee_id": emp["employee_id"],
            "role": emp["role"],
            "department": emp["department"],
            "employment_type": emp["employment_type"],
            "employment_status": emp.get("employment_status"),
            "location": emp["location"],
            "fwa_eligible": emp["fwa_eligible"],
        }

    return {
        "topic": topic,
        "context": context,
        "employee_context": employee_context,
        "policy_evidence": [
            {
                "doc_id": r.doc_id,
                "doc_title": r.doc_title,
                "section": r.section,
                "snippet": r.snippet,
                "score": r.combined_score,
            }
            for r in results
        ],
    }
