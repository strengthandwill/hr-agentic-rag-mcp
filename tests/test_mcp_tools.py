"""MCP tool discovery + live tool call test, run over the real stdio transport (not direct
Python function calls), per the CI/CD rubric requirement."""
import pytest

from app.mcp_client.client import create_mcp_client

EXPECTED_TOOL_NAMES = {
    "search_policy_documents",
    "get_policy_section",
    "check_policy_compliance",
    "lookup_employee_profile",
    "check_pto_balance",
    "lookup_benefits_status",
    "create_mock_hr_ticket",
    "draft_hr_email",
}


async def test_mcp_discovers_all_eight_tools():
    async with create_mcp_client() as client:
        tools = await client.discover_tools()
        names = {t["function"]["name"] for t in tools}
        assert names == EXPECTED_TOOL_NAMES


async def test_mcp_call_lookup_employee_profile():
    async with create_mcp_client() as client:
        result = await client.call_tool("lookup_employee_profile", {"employee_id": "E001"})
        assert result["found"] is True
        assert result["employee_id"] == "E001"
        assert result["name"] == "Alice Tan"


async def test_mcp_call_unknown_employee_returns_graceful_error():
    async with create_mcp_client() as client:
        result = await client.call_tool("check_pto_balance", {"employee_id": "E999"})
        assert result["found"] is False
        assert "E999" in result["message"]


async def test_mcp_call_search_policy_documents_returns_citable_results():
    async with create_mcp_client() as client:
        result = await client.call_tool(
            "search_policy_documents", {"query": "annual leave entitlement", "top_k": 3}
        )
        assert len(result["results"]) > 0
        assert result["results"][0]["doc_id"] == "POL-PTO-01"


async def test_mcp_create_ticket_requires_confirmation():
    async with create_mcp_client() as client:
        preview = await client.call_tool(
            "create_mock_hr_ticket",
            {"employee_id": "E001", "category": "pto", "summary": "test ticket", "confirmed": False},
        )
        assert preview["status"] == "preview_only"

        created = await client.call_tool(
            "create_mock_hr_ticket",
            {"employee_id": "E001", "category": "pto", "summary": "test ticket", "confirmed": True},
        )
        assert created["status"] == "created"
        assert created["ticket"]["ticket_id"].startswith("TCK-")
