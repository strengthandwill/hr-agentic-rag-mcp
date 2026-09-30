"""CPDA HR MCP server -- exposes 8 tools over stdio using the official MCP Python SDK.

Run directly for local testing:
    python -m mcp_server.server

The agent (app/mcp_client/client.py) spawns this module as a subprocess and communicates over
stdio using the MCP protocol (list_tools / call_tool), so every tool invocation is a real MCP
round trip rather than a direct Python function call.
"""
from mcp.server.fastmcp import FastMCP

from app.config import RETRIEVAL_TOP_K
from mcp_server.tools import action_tools, employee_tools, policy_tools

mcp = FastMCP("cpda-hr-tools")


@mcp.tool()
def search_policy_documents(query: str, top_k: int = RETRIEVAL_TOP_K, doc_id: str | None = None) -> dict:
    """Search the CPDA policy corpus (RAG) and return top matching chunks with doc_id/section citations."""
    return policy_tools.search_policy_documents(query, top_k=top_k, doc_id=doc_id)


@mcp.tool()
def get_policy_section(doc_id: str, section: str | None = None) -> dict:
    """Fetch the full text of a policy document by doc_id (e.g. 'POL-PTO-01'), optionally one section."""
    return policy_tools.get_policy_section(doc_id, section=section)


@mcp.tool()
def check_policy_compliance(topic: str, employee_id: str | None = None, context: str | None = None) -> dict:
    """Gather policy evidence and employee context for a compliance question (e.g. expense, remote work)."""
    return policy_tools.check_policy_compliance(topic, employee_id=employee_id, context=context)


@mcp.tool()
def lookup_employee_profile(employee_id: str) -> dict:
    """Look up a CPDA employee's profile: role, department, employment type, manager, location."""
    return employee_tools.lookup_employee_profile(employee_id)


@mcp.tool()
def check_pto_balance(employee_id: str) -> dict:
    """Check a CPDA employee's Annual Leave (PTO) and related leave balances."""
    return employee_tools.check_pto_balance(employee_id)


@mcp.tool()
def lookup_benefits_status(employee_id: str) -> dict:
    """Check a CPDA employee's benefits elections: medical, dental, wellness, dependents."""
    return employee_tools.lookup_benefits_status(employee_id)


@mcp.tool()
def create_mock_hr_ticket(employee_id: str, category: str, summary: str, confirmed: bool = False) -> dict:
    """Create a mock HR ticket for human follow-up. Only call with confirmed=true after the user
    has explicitly agreed in this conversation; otherwise this returns a preview without creating anything."""
    return action_tools.create_mock_hr_ticket(employee_id, category, summary, confirmed=confirmed)


@mcp.tool()
def draft_hr_email(to: str, subject: str, context: str, employee_id: str | None = None) -> dict:
    """Draft (never send) an HR-related email for the user to review. Always a mock draft."""
    return action_tools.draft_hr_email(to, subject, context, employee_id=employee_id)


if __name__ == "__main__":
    mcp.run()
