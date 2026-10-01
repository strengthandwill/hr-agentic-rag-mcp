# Design & Evaluation

## 1. Architecture

```
                         ┌──────────────────────────────────────────────────────┐
                         │              Single Render/Railway process           │
                         │                                                      │
Browser  ── HTTP ──►     │  FastAPI web app (app/main.py)                       │
 chat UI  /chat /health  │    - serves static chat UI                          │
                         │    - /chat, /health endpoints                       │
                         │           │                                          │
                         │           ▼                                          │
                         │  Agent orchestrator (app/agent/orchestrator.py)      │
                         │    - manual ReAct-style tool-calling loop            │
                         │    - Groq LLM client (app/agent/llm_client.py)       │
                         │    - builds operational trace + citations            │
                         │           │  MCP protocol (list_tools / call_tool)   │
                         │           ▼                                          │
                         │  MCP client (app/mcp_client/client.py)               │
                         │    - spawns MCP server as a stdio subprocess         │
                         │           │  stdio                                   │
                         │           ▼                                          │
                         │  MCP server (mcp_server/server.py, FastMCP, 8 tools) │
                         │      │                              │                │
                         │      ▼                              ▼                │
                         │  RAG tools (app/rag/*)        Mock-data tools        │
                         │   - Chroma persistent store    (mcp_server/          │
                         │   - local ONNX MiniLM embed.    tools/employee_*,    │
                         │   - corpus/*.md|html|txt        action_*.py)         │
                         │                                 - mock_data/*.json   │
                         └──────────────────────────────────────────────────────┘
                                           │
                                           ▼
                                   Groq API (LLM provider,
                                   OpenAI-compatible tool calling)
```

The web app, agent orchestrator, MCP client, RAG index, and mock data all run in one process;
the MCP server runs as a stdio **subprocess** of that process (spawned by
`app/mcp_client/client.py`), so tool calls are genuine MCP protocol round trips rather than
direct Python function calls — the agent has no import path into `mcp_server/tools/*`.

## 2. RAG design

- **Corpus**: 15 synthetic policy documents in `corpus/` (13 Markdown, 1 HTML, 1 TXT — satisfying
  "at least two supported source formats"), totaling ~15,300 words (roughly 35-45 pages at a
  realistic 350-430 words/page for formatted markdown with headers/tables/bullets), within the
  assignment's 5-20 file / 30-120 page range. Covers PTO, holidays, remote/flexi-work, expenses,
  business travel, data security, benefits, onboarding, equipment, family leave, workplace
  conduct, anti-harassment/non-discrimination, performance management & probation, HR case
  escalation, and manager approval routing. Each document includes a Worked Examples section and
  a Frequently Asked Questions section in addition to its core policy text, which both adds
  realistic depth and gives the retriever more diverse phrasings to match against real employee
  questions. Documents cross-reference each other by `doc_id` (e.g. `POL-PTO-01`), which supports
  realistic multi-document questions.
- **Parsing**: format-specific parsers (`app/rag/chunking.py`) extract a `doc_id`/`title`/
  `category` from each document's metadata header and split the body into `(heading, text)`
  sections — Markdown on `## ` headings, HTML on `<h2>`, plain text on numbered `N. HEADING`
  lines.
- **Chunking strategy (justification)**: heading-aware sections are the retrieval/citation unit,
  because each section of a policy document is written to answer one specific question, so a
  citation pointing at a section is meaningful to a reader. Any section longer than
  `CHUNK_TOKEN_SIZE` (400, word-count proxy for tokens) words is further split into overlapping
  windows (`CHUNK_TOKEN_OVERLAP`=60 words) so no chunk is too large for consistent retrieval
  granularity. Chunking is fully deterministic (no randomness) — the same corpus always produces
  the same chunk IDs and content. On the generation side, `app/agent/llm_client.py` passes a
  fixed `seed` (`RANDOM_SEED`, default 42, env-overridable) on every Groq call, so the "fixed
  seeds where applicable" requirement is satisfied at both the deterministic-chunking stage and
  the LLM-generation stage.
- **Embeddings**: Chroma's bundled default embedding function — a local ONNX MiniLM model — was
  chosen deliberately over `sentence-transformers`/torch specifically to keep memory usage low
  enough for a Render/Railway free-tier instance (which can have as little as 512MB RAM); it's
  still fully local (no API key, no per-call cost) and deterministic.
- **Vector store**: Chroma `PersistentClient`, one collection (`cpda_policy_chunks`), persisted
  to `data/chroma/` (rebuilt from the committed corpus on every deploy/startup — no reliance on a
  paid database).
- **Retrieval (`app/rag/retriever.py`)**: top-k vector search (`RETRIEVAL_TOP_K=5` default) with a
  lightweight rerank: `combined_score = 0.7 * vector_similarity + 0.3 * keyword_overlap`, so
  chunks containing the user's exact terms aren't out-ranked by purely semantic neighbours — an
  appropriate, explainable reranker for a small, well-structured policy corpus.
- **Guardrails**: the agent's system prompt (`app/agent/prompts.py`) requires every policy
  statement to be grounded in a tool result from the current conversation, requires inline
  `[doc_id §section]` citations, instructs the model to say clearly when the corpus has no
  relevant information (out-of-corpus refusal) rather than use outside knowledge, and requires
  responses to separate "Policy fact:" statements from "Recommendation:" statements.

## 3. MCP server design

- **Transport**: stdio (official `mcp` Python SDK, `FastMCP` high-level server API), matching the
  assignment's recommended free-tier architecture. The client (`app/mcp_client/client.py`) spawns
  `python -m mcp_server.server` as a subprocess via `StdioServerParameters`, then uses
  `ClientSession.list_tools()` / `.call_tool()` for real protocol round trips.
- **Tool discovery**: `MCPToolClient.discover_tools()` calls `list_tools()` and converts each MCP
  `Tool` (name, description, JSON-schema `inputSchema`) into an OpenAI/Groq-compatible
  `{"type": "function", "function": {...}}` entry, which is passed directly as the `tools=`
  argument to the Groq chat-completions call — so the LLM's available actions are always exactly
  what the MCP server currently exposes, discovered at runtime, not hard-coded in the prompt.
- **8 tools exposed** (`mcp_server/server.py`, implementations in `mcp_server/tools/*.py`):

  | Tool | Category | Notes |
  |---|---|---|
  | `search_policy_documents(query, top_k, doc_id?)` | RAG | top-k retrieval with citations |
  | `get_policy_section(doc_id, section?)` | RAG | fetch full text of a doc/section |
  | `check_policy_compliance(topic, employee_id?, context?)` | RAG + mock data | bundles policy evidence with employee context; does not itself issue a yes/no ruling |
  | `lookup_employee_profile(employee_id)` | Mock data | role, dept, employment type, manager, location |
  | `check_pto_balance(employee_id)` | Mock data | annual/family/compassionate leave balances |
  | `lookup_benefits_status(employee_id)` | Mock data | medical/dental/wellness/dependents |
  | `create_mock_hr_ticket(employee_id, category, summary, confirmed)` | Mock action | irreversible-action guardrail: no-op preview unless `confirmed=true` |
  | `draft_hr_email(to, subject, context, employee_id?)` | Mock action | always a draft only; nothing is ever sent |

- **Schemas**: generated automatically by FastMCP from each tool function's type hints and
  docstring (Pydantic-based JSON schema), so the schema the LLM sees is always in sync with the
  actual function signature.
- **Failure handling**: `MCPToolClient.call_tool` catches transport errors and MCP `isError`
  responses and raises a typed `MCPToolCallError`; the orchestrator catches that per tool call,
  logs it in the trace with the error message, and feeds a graceful-degradation message back to
  the LLM ("this tool is currently unavailable...") instead of crashing the request.

## 4. Agent orchestration design

- **No agent framework** (no LangChain/LlamaIndex/etc.) — `app/agent/orchestrator.py` implements
  a manual ReAct-style loop directly against Groq's OpenAI-compatible `tools=` API. This was a
  deliberate choice: it keeps every step of the loop as plain, auditable code, which makes it
  straightforward to build an accurate operational trace (exactly which tool, with which
  arguments, returned what, in what order, with what latency) rather than trying to reverse an
  opaque framework's internal callback structure.
- **Loop**: system prompt + conversation history + new user message → Groq chat completion with
  `tools=` → if the model returns `tool_calls`, execute each via the MCP client, append the tool
  result as a `role: tool` message, loop again (bounded by `AGENT_MAX_TOOL_ITERATIONS=6`); once
  the model returns plain content with no tool calls, that's the final answer.
- **Trace**: each tool call becomes one entry — `{step, tool, arguments, result_summary,
  latency_ms, error}` — returned to the client under `trace` and rendered in a collapsible panel
  in the chat UI. Retrieved-policy tool results are additionally deduped into a `citations` list
  by `(doc_id, section)`.
- **Session/confirmation state**: `app/agent/session_store.py` keeps an in-memory per-`session_id`
  message history (process-local; resets on restart — acceptable for a free-tier demo). No
  separate "pending confirmation" flag is needed: the confirmation guardrail (below) falls out
  naturally from normal multi-turn conversation history plus the tool's own safety check.
- **Failure/ambiguity handling**: if a tool reports "employee not found" or an unclear request,
  the system prompt instructs the model to ask a clarifying question rather than guess; the
  `expect_clarification` eval category checks this behavior explicitly (§6).

## 5. Safety guardrails

- **Irreversible actions require confirmation**: `create_mock_hr_ticket` takes a `confirmed`
  argument that defaults to `false`. The system prompt instructs the agent to always call it
  first with `confirmed=false` (a preview, no write happens), describe the preview to the user,
  and ask for explicit confirmation; only after the user affirmatively agrees in a later message
  does the agent call it again with `confirmed=true`. This is enforced in the **tool
  implementation itself** (`mcp_server/tools/action_tools.py`), not only as a prompt suggestion —
  a prompt-injected or confused model still cannot write a ticket without that argument being
  explicitly set to `true`.
- **`draft_hr_email` never sends anything** — there is no email-sending code in this repository;
  it only returns templated text for the user to review.
- **Out-of-corpus refusal**: the system prompt requires the agent to say plainly when the corpus
  has no relevant information, instead of answering from general knowledge.
- **Sensitive HR matters** (harassment, discrimination, safety): the prompt instructs the agent
  to respond with empathy, cite the Workplace Conduct Code and HR Case escalation process
  (`POL-CONDUCT-09`, `POL-HRTRIAGE-11`), and make clear a human People & Culture officer must be
  involved rather than let the model adjudicate the situation itself.

## 6. Two demo workflows

### Workflow A — PTO request guidance
**User**: "I am employee E001. Can I take 3 days of PTO next week?"
**Expected tool sequence**: `check_pto_balance(employee_id="E001")` →
`search_policy_documents(query≈"PTO request advance notice", ...)` → cited answer combining the
employee's actual balance (12.5 days) with the policy's advance-notice rule (`POL-PTO-01 §3`).

### Workflow B — Remote work eligibility (multi-document, overseas)
**User**: "I am employee E002. I want to work from Indonesia for 6 weeks starting next month, is that allowed?"
**Expected tool sequence**: `lookup_employee_profile(employee_id="E002")` →
`check_policy_compliance(topic="overseas remote work", employee_id="E002", ...)` (bundles policy
evidence from `POL-FWA-03`/`POL-SEC-05`/`POL-APPROVAL-12` with the employee's role/employment
context) → cited answer explaining the request exceeds the 20-working-day annual overseas cap and
needs a formal exception with Head of Department + People & Culture sign-off.

Both are reproducible via the chat UI's quick-prompt buttons or `POST /chat` (see README).

## 7. Deployment

Single Render (or equivalent) free-tier web service running the web app, agent orchestrator, MCP
client/server subprocess, Chroma index, and mock JSON data together, per the assignment's
recommended free-tier architecture (`render.yaml`, `Procfile`). See `deployed.md` for the live
URL, environment variables, and cold-start behavior.

## 8. Evaluation

### Methodology

`evaluation/eval_questions.jsonl` contains 27 questions/tasks across five categories: simple
policy Q&A (8), multi-document questions (4), tool-requiring workflows (8), ambiguous requests
(3), and out-of-scope requests (4) — each with expected cited `doc_id`s, expected MCP tools,
gold keywords, and/or expected behavior flags (clarification / refusal / confirmation-prompt).
`evaluation/run_eval.py` sends each question to the running app's `/chat` endpoint and scores:

- **Citation accuracy** — fraction of a question's expected `doc_id`s that appear in the
  response's citations.
- **Groundedness (keyword match)** — fraction of a question's gold keywords present in the
  answer text (a fast proxy for groundedness; the full response text is also inspectable by hand
  in `eval_run_output.json` for spot-checking).
- **Tool-selection accuracy** — fraction of a question's expected MCP tools that appear in the
  actual tool-call trace.
- **Workflow completion rate** — for `tool_workflow` questions, whether the expected tools were
  used and a non-empty answer was produced.
- **Clarification accuracy** — for `ambiguous` questions, whether the agent asked a clarifying
  question instead of calling tools with guessed/missing information.
- **Refusal accuracy** — for `out_of_scope` questions, whether the agent declined without calling
  any tools.
- **Action-safety pass rate** — for the ticket-creation question, whether the agent previewed and
  asked for confirmation rather than creating the ticket outright on the first turn.
- **Latency p50/p95** — wall-clock `/chat` request latency across all 27 questions.

### Results

See [`evaluation/results.md`](evaluation/results.md) for the actual numbers from a real run
against the deployed/local app (not estimated), plus the retrieval-`top_k` ablation
(`top_k=3` vs `top_k=6`, measured as citation hit-rate against the retriever directly).
