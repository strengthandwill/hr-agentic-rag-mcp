# CPDA HR Assistant — Agentic RAG + MCP (Course Project)

An agentic AI system that helps employees of **CivicPulse Digital Agency (CPDA)** — a wholly
**fictional** Singapore government-technology agency created for this course project (loosely
inspired by publicly reported GovTech Singapore HR practices, e.g. flexi-work terminology and
leave categories) — complete HR policy and operations tasks. It combines:

- **Policy RAG** over a 12-document synthetic policy corpus (Markdown/HTML/TXT), with citations.
- **An agent orchestrator** that plans, selects tools, calls **MCP-exposed tools** over stdio,
  and synthesizes grounded, cited answers.
- **Mock structured HR data** (employees, PTO balances, benefits elections, HR tickets) — all
  synthetic.

> No real company, employee, or private data is used anywhere in this repository.

See also: [`design-and-evaluation.md`](design-and-evaluation.md) (architecture, RAG/MCP/agent
design, evaluation results), [`ai-tooling.md`](ai-tooling.md) (how AI coding tools were used),
[`deployed.md`](deployed.md) (live URL + cold-start notes), [`demo-script.md`](demo-script.md)
(talking points for the recorded demo).

## Architecture at a glance

```
Browser (chat UI) ── /chat, /health ── FastAPI app (app/main.py)
                                          │
                                agent orchestrator (app/agent)
                                 - Groq LLM (tool-calling loop)
                                          │  MCP protocol over stdio
                                          ▼
                              MCP client  ──spawns──  MCP server (mcp_server/server.py)
                                                          │
                                        ┌─────────────────┴─────────────────┐
                                        ▼                                   ▼
                          RAG tools (app/rag: Chroma +            Mock-data tools
                          local ONNX MiniLM embeddings,           (mock_data/*.json:
                          over corpus/*.md|html|txt)               employees, PTO,
                                                                    benefits, tickets)
```

All of the above runs in a **single process** (per the assignment's recommended free-tier
architecture): the web app, agent orchestrator, and MCP client run in the main process; the MCP
server runs as a stdio subprocess spawned by the MCP client.

## Prerequisites

- Python 3.12 (3.13/earlier 3.x should also work; 3.14 is **not** yet supported by some pinned
  dependencies as of this writing).
- A free Groq API key: https://console.groq.com/keys

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set GROQ_API_KEY=<your key>
```

## Running locally

```bash
# (optional -- the app auto-builds the index on first startup if missing)
python -m app.rag.ingest

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 for the chat UI. Try the quick-prompt buttons, or:

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool

curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "I am employee E001. Can I take 3 days of PTO next week?"}' | python3 -m json.tool
```

### Running the MCP server standalone (for inspection)

```bash
python -m mcp_server.server
```

This starts the MCP server over stdio; it's normally spawned automatically by the app.

## Running tests

```bash
pytest -q
```

Covers: app start/health check, MCP tool discovery + live tool calls over real stdio MCP
transport, corpus parsing/chunking correctness, and (if `GROQ_API_KEY` is set) a full live
agent-turn smoke test.

## Running the evaluation suite

```bash
# terminal 1
uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2
python evaluation/run_eval.py --base-url http://127.0.0.1:8000
```

Writes `evaluation/eval_run_output.json` (raw per-question results) and prints a summary; see
[`design-and-evaluation.md`](design-and-evaluation.md) and
[`evaluation/results.md`](evaluation/results.md) for the write-up.

## Deployment

See [`deployed.md`](deployed.md) for the live URL and [`design-and-evaluation.md`](design-and-evaluation.md#deployment)
for the Render deployment architecture. Quick summary: single Render free web service, build
command `pip install -r requirements.txt`, start command
`python -m app.rag.ingest && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
(see `render.yaml` / `Procfile`), with `GROQ_API_KEY` set as a Render environment variable/secret.

## Repository layout

```
app/            FastAPI web app, RAG pipeline, agent orchestrator, MCP client
mcp_server/     MCP server exposing 8 tools (policy RAG + mock structured data + mock actions)
corpus/         Synthetic policy documents (12 files: .md / .html / .txt)
mock_data/      Synthetic employees, PTO balances, benefits elections, ticket seed data
evaluation/     25+ eval questions, eval runner script, results write-up
tests/          pytest suite (health/start, MCP discovery+call, RAG parsing, agent smoke)
.github/workflows/ci.yml   CI: install, import/build check, ingest, tests, gated deploy trigger
```

## Reproducing the two required agentic demo tasks

1. **PTO request guidance** — send `I am employee E001. Can I take 3 days of PTO next week?`
   (or click the "PTO request (E001)" quick-prompt button in the UI).
2. **Remote work eligibility (multi-document, overseas)** — send
   `I am employee E002. I want to work from Indonesia for 6 weeks starting next month, is that allowed?`
   (or click the "Remote work eligibility (E002)" quick-prompt button).

Both are reproducible via the chat UI or directly via `POST /chat` as shown above. See
[`design-and-evaluation.md`](design-and-evaluation.md#two-demo-workflows) for the expected
MCP tool-call sequence for each.

## AI tooling disclosure

This project was built with substantial assistance from Claude Code. See
[`ai-tooling.md`](ai-tooling.md) for details on what was AI-assisted vs. human-reviewed.
