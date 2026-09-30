"""Thin async wrapper around the Groq chat-completions API (OpenAI-compatible tool calling).

Includes small retry/backoff for transient 429 rate-limit responses: Groq's free tier enforces a
tokens-per-minute cap, which a burst of agent turns (each needing 1-3 sequential completions) can
occasionally hit. A brief retry turns that into a slightly slower response instead of a failed
request, which is the graceful-degradation behavior expected of the agent layer.
"""
from __future__ import annotations

import asyncio

from groq import APIStatusError, AsyncGroq

from app.config import GROQ_API_KEY, GROQ_MODEL

_client: AsyncGroq | None = None

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0


def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


async def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    temperature: float = 0.2,
    model: str | None = None,
):
    client = get_client()
    kwargs: dict = {
        "model": model or GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return await client.chat.completions.create(**kwargs)
        except APIStatusError as exc:
            last_exc = exc
            if exc.status_code == 429 and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BASE_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
    raise last_exc  # pragma: no cover
