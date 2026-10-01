"""App start / health smoke test.

Uses FastAPI's TestClient as a context manager so the app's lifespan (which builds the RAG
index if needed and spawns the MCP server subprocess) actually runs, giving a real end-to-end
"can the app start" check as required by the CI/CD rubric item.
"""
from fastapi.testclient import TestClient

from app.config import GROQ_API_KEY
from app.main import app


def test_health_endpoint_reports_ready_app():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

        data = resp.json()
        assert data["app"] == "cpda-hr-assistant"
        assert data["mcp_connected"] is True
        assert data["mcp_tool_count"] == 8
        assert data["rag_index_ready"] is True
        assert data["rag_chunk_count"] > 0
        assert data["groq_api_key_configured"] is bool(GROQ_API_KEY)
        expected_status = "ok" if GROQ_API_KEY else "degraded"
        assert data["status"] == expected_status


def test_index_page_serves():
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"CPDA" in resp.content or b"HR Assistant" in resp.content
