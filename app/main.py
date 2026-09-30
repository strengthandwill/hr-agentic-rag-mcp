"""FastAPI web application: chat UI, /chat API, /health API.

Wires together the RAG index, the MCP client (which spawns the MCP server subprocess), and the
agent orchestrator. Runs as a single process, per the assignment's recommended free-tier
architecture.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.orchestrator import run_agent_turn
from app.mcp_client.client import create_mcp_client
from app.rag import vector_store
from app.rag.ingest import run_ingest

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app_state: dict = {"mcp_client": None, "mcp_cm": None, "call_lock": None, "started_at": None}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    if vector_store.count() == 0:
        print("Vector store empty on startup -- running ingest...")
        run_ingest()

    cm = create_mcp_client()
    mcp_client = await cm.__aenter__()
    app_state["mcp_cm"] = cm
    app_state["mcp_client"] = mcp_client
    app_state["call_lock"] = asyncio.Lock()
    app_state["started_at"] = time.time()
    try:
        await mcp_client.discover_tools()
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: MCP tool discovery failed at startup: {exc}")

    yield

    with contextlib.suppress(Exception):
        await cm.__aexit__(None, None, None)


app = FastAPI(title="CPDA HR Assistant", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[dict]
    trace: list[dict]
    escalated: bool
    latency_ms: int


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    mcp_client = app_state.get("mcp_client")
    mcp_connected = False
    tool_count = 0
    if mcp_client is not None:
        try:
            tools = await mcp_client.discover_tools()
            mcp_connected = True
            tool_count = len(tools)
        except Exception:  # noqa: BLE001
            mcp_connected = False

    try:
        chunk_count = vector_store.count()
        rag_ok = True
    except Exception:  # noqa: BLE001
        chunk_count = 0
        rag_ok = False

    uptime = time.time() - app_state["started_at"] if app_state.get("started_at") else 0

    return {
        "status": "ok" if (mcp_connected and rag_ok) else "degraded",
        "app": "cpda-hr-assistant",
        "mcp_connected": mcp_connected,
        "mcp_tool_count": tool_count,
        "rag_index_ready": rag_ok,
        "rag_chunk_count": chunk_count,
        "uptime_seconds": round(uptime, 1),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    mcp_client = app_state["mcp_client"]
    lock: asyncio.Lock = app_state["call_lock"]

    start = time.time()
    async with lock:
        result = await run_agent_turn(session_id, req.message, mcp_client)
    latency_ms = int((time.time() - start) * 1000)

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        citations=result["citations"],
        trace=result["trace"],
        escalated=result["escalated"],
        latency_ms=latency_ms,
    )
