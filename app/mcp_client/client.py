"""MCP client wrapper: spawns the CPDA MCP server as a stdio subprocess and exposes a small
async API the agent orchestrator uses to discover and call MCP tools.

This is the *only* way the agent invokes tool logic -- there is no direct Python import path
from app/agent/* into mcp_server/tools/*, so every tool call is a genuine MCP protocol round
trip (list_tools / call_tool over stdio), satisfying the assignment's "must actually call
MCP-exposed tools" requirement.
"""
from __future__ import annotations

import json
import shlex
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import MCP_SERVER_CMD


class MCPToolCallError(Exception):
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"MCP tool '{tool_name}' failed: {message}")


class MCPToolClient:
    """Thin async wrapper around an initialized mcp.ClientSession."""

    def __init__(self, session: ClientSession):
        self._session = session
        self._tools_cache: list[dict] | None = None

    async def discover_tools(self) -> list[dict]:
        """Return tool schemas in OpenAI/Groq function-calling format. Cached after first call."""
        if self._tools_cache is not None:
            return self._tools_cache
        result = await self._session.list_tools()
        openai_tools = []
        for tool in result.tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema
                        or {"type": "object", "properties": {}},
                    },
                }
            )
        self._tools_cache = openai_tools
        return openai_tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Call an MCP tool by name and return its parsed JSON result (a plain dict)."""
        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:  # MCP transport / server crash
            raise MCPToolCallError(name, f"transport error: {exc}") from exc

        if result.isError:
            text = _first_text(result.content) or "unknown error"
            raise MCPToolCallError(name, text)

        text = _first_text(result.content)
        if text is None:
            return {"error": "empty_tool_response"}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw_text": text}


def _first_text(content_blocks) -> str | None:
    for block in content_blocks:
        if getattr(block, "type", None) == "text":
            return block.text
    return None


@asynccontextmanager
async def create_mcp_client(server_cmd: str = MCP_SERVER_CMD):
    """Async context manager: spawns the MCP server subprocess, yields a connected MCPToolClient."""
    parts = shlex.split(server_cmd)
    params = StdioServerParameters(command=parts[0], args=parts[1:])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield MCPToolClient(session)
