# AI Tooling Disclosure

## Summary

This project was built with **Claude Code** (Anthropic's agentic CLI, running Claude Sonnet 5)
as the primary development tool, operating under direct human instruction and review throughout.
Per the assignment's plagiarism policy ("Use of AI tools is permitted... students must describe
their use of AI tooling... and remain responsible for the correctness, security, and academic
integrity of the submitted work"), this document describes what the tool did, what worked well,
what didn't, and what human review/decisions shaped the result.

## What Claude Code did

- **Research**: Web-searched publicly available information about GovTech Singapore (careers
  pages, Glassdoor reviews, public-sector flexi-work terminology) to ground the fictional CPDA
  company's policies and mock data in realistic, plausible HR practices, while keeping the
  company, employees, and all data entirely fictional/synthetic per the assignment's requirements.
- **Architecture and design decisions**: proposed the stack (FastAPI, Groq, Chroma with the
  bundled local ONNX embedding function, the official `mcp` Python SDK over stdio, manual
  ReAct-style tool-calling loop instead of a heavier agent framework), and explained the
  reasoning for each choice (mainly: staying within free-tier compute/memory limits while using
  a real MCP protocol implementation rather than a simulated one). These were presented to the
  human operator as a plan and approved before implementation began.
- **Implementation**: wrote essentially all code in this repository — the RAG chunking/embedding/
  retrieval pipeline, the 8 MCP tools and server, the agent orchestrator and system prompt, the
  FastAPI app and vanilla-JS chat UI, the pytest suite, the GitHub Actions workflow, the 12-file
  policy corpus, the synthetic mock datasets, the 27-question evaluation set and evaluation
  runner, and this documentation set.
- **Testing and debugging**: created a local Python 3.12 virtual environment, ran the ingestion
  pipeline, the MCP server, and the FastAPI app locally, and iteratively fixed real bugs it found
  by actually running the code (not just by inspection) — see "What didn't work smoothly" below.
- **Evaluation**: ran the evaluation script against the live local app and used the real output
  to write up `evaluation/results.md`, rather than inventing plausible-looking numbers.

## What worked well

- Having Claude Code actually execute the code at each stage (ingest a real corpus, spawn a real
  MCP subprocess, call a real Groq API, hit real HTTP endpoints) caught several bugs that would
  not have been visible from a code review alone (see below), and produced evaluation numbers
  that reflect the actual system rather than an estimate.
- Generating the policy corpus and mock data together, with consistent cross-references (doc IDs,
  section numbers, employee IDs) between them, made it straightforward to write eval questions
  whose gold citations and expected tool sequences are actually correct.

## What didn't work smoothly (and required intervention/human decisions)

- **Python version incompatibility**: the system's default Python was 3.14, for which one of
  Chroma's transitive dependencies (`tokenizers`, a Rust extension) had no prebuilt wheel yet.
  Resolved by creating the virtual environment with Python 3.12 instead.
- **`mcp` package version**: the initially pinned `mcp==1.1.2` predates the high-level `FastMCP`
  server API used in `mcp_server/server.py`; upgraded to `mcp==1.9.4` after checking available
  versions, and had to remove a stray `from __future__ import annotations` in `server.py` that
  broke FastMCP's runtime type introspection for `X | None` parameters.
- **Metadata-extraction regex bug**: the first version of the corpus metadata parser
  (`app/rag/chunking.py`) mis-parsed the `**Document ID:**` markdown field, causing every chunk
  to be tagged `doc_id="unknown"` and silently colliding IDs across documents. Caught by actually
  running ingest and inspecting the (very wrong) output, then fixed and re-verified with a
  dedicated pytest test (`test_all_corpus_files_parse_without_unknown_doc_id`).
- **Groq model name**: the originally planned model (`llama-3.3-70b-versatile`) is no longer
  served on the free tier; Claude Code queried the account's available models via the Groq API
  and switched the default to `openai/gpt-oss-120b`, which supports tool calling.
- **Tool-call pattern for the remote-work workflow**: the first end-to-end test of the "remote
  work eligibility" demo task showed the agent answering correctly but skipping
  `lookup_employee_profile`/`check_policy_compliance` in favor of only `search_policy_documents`.
  The system prompt was tightened with an explicit tool-sequencing pattern for eligibility/
  compliance questions, re-tested, and confirmed to produce the intended multi-tool trace.

## Human responsibility

The person submitting this project reviewed the generated architecture, ran the app and tests
themselves, supplied their own Groq API key, and is responsible for the deployment, the GitHub
repository sharing/submission, and the recorded demo video, none of which Claude Code can do on
a user's behalf.
