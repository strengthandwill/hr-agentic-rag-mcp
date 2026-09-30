# Demo Video Script (7–10 minutes)

Talking points for the required recorded screen-share demo. Adjust employee names/IDs and
personalize as needed; all group members must speak and show government ID per the submission
guidelines (not something this document can do for you).

## 0. Intro (30–45s)

- State names, and show government ID on camera (submission requirement).
- "We built an agentic HR assistant for CivicPulse Digital Agency, a fictional Singapore
  govtech-style company, combining policy RAG with MCP tool calling over mock HR data."
- Show the deployed URL loading (from `deployed.md`) — mention cold-start note if relevant.

## 1. Architecture walkthrough (60–90s)

- Show the architecture diagram/text in `design-and-evaluation.md`.
- Call out: FastAPI web app + agent orchestrator in one process; MCP server spawned as a stdio
  subprocess exposing 8 tools; Chroma vector store built from the committed policy corpus with a
  local embedding model (no external embedding API); Groq as the LLM provider with real
  OpenAI-compatible tool calling.
- Mention: no framework (LangChain etc.) for the agent loop — it's a manual tool-calling loop so
  every step can be logged into an explicit trace.

## 2. Demo Task 1 — PTO Request Guidance (≈2 min)

1. In the chat UI, send: **"I am employee E001. Can I take 3 days of PTO next week?"**
2. While it runs, narrate: the agent should call `check_pto_balance` (mock structured data tool)
   and `search_policy_documents` (RAG tool).
3. Expand the **trace** panel under the response. Point at:
   - Tool name `check_pto_balance`, argument `{"employee_id": "E001"}`, and the returned balance
     (12.5 days).
   - Tool name `search_policy_documents`, its query argument, and the returned chunk from
     `POL-PTO-01 §3` (advance-notice rule).
4. Expand **citations** and show `[POL-PTO-01 §3]` backing the "submit 2 weeks in advance"
   statement, and point out the answer's "Policy fact" vs "Recommendation" split.

## 3. Demo Task 2 — Remote Work Eligibility (multi-document, overseas) (≈2 min)

1. Send: **"I am employee E002. I want to work from Indonesia for 6 weeks starting next month, is that allowed?"**
2. Narrate the expected trace: `lookup_employee_profile` (mock data tool) →
   `check_policy_compliance` (RAG + employee-context tool).
3. Show the trace panel: tool names, the `employee_id` argument, and the retrieved policy
   evidence bundle spanning **multiple documents** — `POL-FWA-03` (overseas cap + approval
   chain), `POL-SEC-05` (VPN/security), `POL-APPROVAL-12` (approval routing).
4. Read out the conclusion: 6 weeks exceeds the 20-working-day annual cap, so it needs a formal
   International Remote Work exception with Head of Department + People & Culture sign-off —
   grounded in the cited sections, not invented.

## 4. Safety guardrail — confirmation before a mock action (≈1 min)

1. Send: **"I am employee E003. Please open an HR ticket asking about my low PTO balance."**
2. Show the agent's first response: a **preview** of the ticket with a "Shall I go ahead?"
   question — no ticket created yet (point at the trace: `create_mock_hr_ticket` called with
   `confirmed: false`).
3. Reply **"Yes, please go ahead."** Show the second response confirming ticket `TCK-100x` was
   created, and the trace showing `confirmed: true` on the second call.
4. Note: this demonstrates the "prevent irreversible actions" requirement — the tool itself
   refuses to create anything without an explicit confirmed flag set only after user agreement.

## 5. Out-of-scope guardrail (≈30s)

- Send: **"What is the capital of France?"**
- Show the agent declining and pointing the user to People & Culture / outside sources instead of
  hallucinating, with an empty tool trace (no wasted/incorrect tool calls).

## 6. CI/CD walkthrough (≈30–45s)

- Show `.github/workflows/ci.yml` and a green run in the GitHub Actions tab: import/build check,
  RAG ingest, pytest (including the MCP discovery + live tool-call test), then the gated deploy
  trigger job.

## 7. Evaluation results walkthrough (≈45–60s)

- Open `evaluation/results.md`. Call out:
  - Groundedness / citation accuracy / tool-selection accuracy / workflow completion / escalation
    accuracy / action-safety pass rate.
  - Latency p50/p95, and the cold-start vs warm-start note.
  - The retrieval-k ablation (top_k=3 vs top_k=6) and what it shows.

## 8. Close (15–20s)

- Recap: RAG + real MCP tool calling + mock data + safety guardrails + free-tier deployment + CI/CD + evaluation, all working end-to-end on the deployed URL.
