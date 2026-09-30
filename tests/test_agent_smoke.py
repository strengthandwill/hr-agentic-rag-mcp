"""Agent orchestrator smoke tests: pure trace/citation helpers always run; a full live agent
turn against Groq only runs when GROQ_API_KEY is set (so CI without the secret still passes,
while a local/CI run with the key exercises the real tool-calling loop end-to-end)."""
import os

import pytest
from groq import RateLimitError

from app.agent.orchestrator import _collect_citations, _summarize_result

requires_groq_key = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY not set; skipping live LLM smoke test"
)


def test_summarize_result_truncates_long_output():
    long_result = {"data": "x" * 1000}
    summary = _summarize_result(long_result, max_len=50)
    assert len(summary) <= 50
    assert summary.endswith("...")


def test_collect_citations_dedupes_by_doc_and_section():
    citations: dict = {}
    search_result = {
        "results": [
            {"doc_id": "POL-PTO-01", "doc_title": "PTO Policy", "section": "3", "snippet": "abc"},
            {"doc_id": "POL-PTO-01", "doc_title": "PTO Policy", "section": "3", "snippet": "abc dup"},
        ]
    }
    _collect_citations(citations, "search_policy_documents", search_result)
    assert len(citations) == 1


@requires_groq_key
async def test_full_agent_turn_pto_workflow():
    from app.mcp_client.client import create_mcp_client
    from app.agent.orchestrator import run_agent_turn

    rate_limit_message = None
    result = None
    async with create_mcp_client() as mcp_client:
        try:
            result = await run_agent_turn(
                "test-session-pto", "I am employee E001. Can I take 3 days of PTO next week?", mcp_client
            )
        except RateLimitError as exc:
            rate_limit_message = str(exc)

    if rate_limit_message is not None:
        pytest.skip(f"Groq free-tier rate limit hit during test run: {rate_limit_message}")

    assert result["answer"]
    tool_names = {step["tool"] for step in result["trace"]}
    assert "check_pto_balance" in tool_names
    assert len(result["citations"]) > 0
