"""Central configuration loaded from environment variables (.env for local dev)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

CORPUS_DIR = BASE_DIR / os.getenv("CORPUS_DIR", "corpus")
MOCK_DATA_DIR = BASE_DIR / os.getenv("MOCK_DATA_DIR", "mock_data")
CHROMA_PERSIST_DIR = BASE_DIR / os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
CHROMA_COLLECTION_NAME = "cpda_policy_chunks"

RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
CHUNK_TOKEN_SIZE = int(os.getenv("CHUNK_TOKEN_SIZE", "400"))
CHUNK_TOKEN_OVERLAP = int(os.getenv("CHUNK_TOKEN_OVERLAP", "60"))

AGENT_MAX_TOOL_ITERATIONS = int(os.getenv("AGENT_MAX_TOOL_ITERATIONS", "6"))

MCP_SERVER_CMD = os.getenv("MCP_SERVER_CMD", "python -m mcp_server.server")

RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

COMPANY_NAME = "CivicPulse Digital Agency (CPDA)"
