"""Manual ReAct-style tool-calling agent loop.

No agent framework (LangChain etc.) is used, by design: every step of the loop is explicit code
here, which makes it straightforward to log a concise, accurate operational trace (selected
tool, arguments, raw result, latency, retrieved citations) for the /chat response and the demo,
per the assignment's "visible or logged trace of agent reasoning steps" requirement.
"""
from __future__ import annotations

import json
import time

from app.agent import llm_client, session_store
from app.agent.prompts import SYSTEM_PROMPT
from app.config import AGENT_MAX_TOOL_ITERATIONS
from app.mcp_client.client import MCPToolCallError, MCPToolClient

CITATION_TOOLS = {"search_policy_documents", "get_policy_section", "check_policy_compliance"}
ACTION_TOOLS = {"create_mock_hr_ticket", "draft_hr_email"}


def _summarize_result(result: dict, max_len: int = 300) -> str:
    try:
        text = json.dumps(result, ensure_ascii=False)
    except TypeError:
        text = str(result)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _collect_citations(citations: dict[str, dict], tool_name: str, result: dict) -> None:
    items = []
    if tool_name == "search_policy_documents":
        items = result.get("results", [])
    elif tool_name == "check_policy_compliance":
        items = result.get("policy_evidence", [])
    elif tool_name == "get_policy_section":
        if result.get("found"):
            for s in result.get("sections", []):
                items.append(
                    {
                        "doc_id": result.get("doc_id"),
                        "doc_title": result.get("doc_title"),
                        "section": s.get("section"),
                        "snippet": s.get("text", "")[:300],
                    }
                )
    for item in items:
        key = f"{item.get('doc_id')}::{item.get('section')}"
        if key not in citations:
            citations[key] = {
                "doc_id": item.get("doc_id"),
                "doc_title": item.get("doc_title"),
                "section": item.get("section"),
                "snippet": item.get("snippet", "")[:300],
            }


def _tool_call_to_message(tool_call) -> dict:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        },
    }


async def run_agent_turn(session_id: str, user_message: str, mcp_client: MCPToolClient) -> dict:
    history = session_store.get_history(session_id)
    tools = await mcp_client.discover_tools()

    messages: list[dict] = (
        [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_message}]
    )

    trace: list[dict] = []
    citations: dict[str, dict] = {}
    escalated = False

    for _ in range(AGENT_MAX_TOOL_ITERATIONS):
        response = await llm_client.chat_completion(messages, tools=tools)
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [_tool_call_to_message(tc) for tc in msg.tool_calls],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                start = time.time()
                error_msg = None
                try:
                    result = await mcp_client.call_tool(name, args)
                except MCPToolCallError as exc:
                    result = {
                        "error": "tool_call_failed",
                        "message": (
                            f"The '{name}' tool is currently unavailable ({exc.message}). "
                            "Let the user know this specific capability failed and, if possible, "
                            "continue with any other information you already have."
                        ),
                    }
                    error_msg = exc.message
                latency_ms = int((time.time() - start) * 1000)

                trace.append(
                    {
                        "step": len(trace) + 1,
                        "tool": name,
                        "arguments": args,
                        "result_summary": _summarize_result(result),
                        "latency_ms": latency_ms,
                        "error": error_msg,
                    }
                )

                if name in CITATION_TOOLS:
                    _collect_citations(citations, name, result)
                if name == "create_mock_hr_ticket" and result.get("status") == "created":
                    if result.get("ticket", {}).get("category") == "conduct":
                        escalated = True

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False)[:4000],
                    }
                )
            continue

        final_answer = msg.content or ""
        messages.append({"role": "assistant", "content": final_answer})
        session_store.set_history(session_id, messages[1:])
        return {
            "answer": final_answer,
            "citations": list(citations.values()),
            "trace": trace,
            "escalated": escalated,
        }

    fallback = (
        "I wasn't able to finish this request within the allowed number of tool calls. "
        "Could you rephrase or split it into smaller questions?"
    )
    messages.append({"role": "assistant", "content": fallback})
    session_store.set_history(session_id, messages[1:])
    return {"answer": fallback, "citations": list(citations.values()), "trace": trace, "escalated": escalated}
