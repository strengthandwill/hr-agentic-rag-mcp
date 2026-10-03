# Demo Video Script — Verbatim Narration + Step-by-Step Actions

Target length: **8–9 minutes** (within the required 7–10 min window). Every section has exact
words to say (**SAY:**) and exact actions to take (**DO:**). Read the SAY lines naturally in your
own voice — they don't need to be word-perfect — but hit every factual claim (tool names,
citations, numbers) exactly as written, since those are what the grader is checking.

**Before you hit record:**
- Open https://cpda-hr-assistant.onrender.com in a browser tab and confirm `/health` shows
  `"status":"ok"` (visit https://cpda-hr-assistant.onrender.com/health directly, or just load the
  homepage and watch the status pill in the header turn green). This also warms up the instance so
  you don't eat a cold-start delay on camera.
- Have a second tab open to the GitHub repo: https://github.com/strengthandwill/hr-agentic-rag-mcp
- Have a third tab ready on the repo's **Actions** tab (for the CI/CD walkthrough) and know how to
  navigate to `evaluation/results.md` and `design-and-evaluation.md` in the repo file browser.
- Have your government ID ready to hold up to the camera (required by the assignment).
- Screen-record your full screen or browser window with your webcam visible in a corner (most
  recorders — QuickTime, Zoom, Loom, OBS — support this).

---

## 0:00–0:45 — Intro and ID check

**DO:** Start the recording with your face on camera. Hold up your government ID clearly to the
camera for a few seconds.

**SAY:**
> "Hi, I'm [your name], and this is my submission for the AI Engineering Techniques and
> Architectures course project. Here's my ID for verification. I built an agentic HR assistant
> for CivicPulse Digital Agency, or CPDA — a fictional Singapore government-technology agency I
> created for this project. It combines policy retrieval-augmented generation, or RAG, with a
> Model Context Protocol, or MCP, tool-calling agent over mock HR data. Let me walk you through
> the architecture, two live demo tasks, the CI/CD pipeline, and the evaluation results."

**DO:** Switch to the browser tab with the deployed app already loaded at
`https://cpda-hr-assistant.onrender.com`.

---

## 0:45–1:45 — Architecture walkthrough

**DO:** Point the cursor at the top of the page: the gray masthead strip, then the navy header
with the status pill.

**SAY:**
> "This is the deployed application. The gray strip at the top is a disclosure that CPDA is a
> fictional company for this course project — not a real government site. Up here in the header,
> this status pill polls the app's health endpoint every sixty seconds and shows that MCP is
> connected with eight tools, and the RAG index has around a hundred seventy chunks loaded."

**DO:** Switch to the GitHub repo tab, open `design-and-evaluation.md`, and scroll to the
architecture diagram near the top.

**SAY:**
> "Architecturally, everything runs as a single process for free-tier compatibility: a FastAPI
> web app serves the chat UI and a slash-chat endpoint. The agent orchestrator runs a manual
> tool-calling loop against Groq as the LLM provider — no agent framework like LangChain, so every
> step is explicit code I can log. The orchestrator talks to an MCP client, which spawns the MCP
> server as a separate subprocess over stdio — that's the real Model Context Protocol, not a
> simulated one. The MCP server exposes eight tools: three backed by the RAG index over our
> policy corpus, three that look up mock employee, PTO, and benefits data, and two mock actions —
> creating an HR ticket and drafting an email — that are gated behind explicit user confirmation."

**DO:** Switch back to the app tab.

---

## 1:45–3:45 — Demo Task 1: PTO request guidance

**SAY:**
> "Let's run the first required agentic task: PTO request guidance. I'm going to use employee
> E001."

**DO:** Click the quick-prompt chip labeled **"PTO request · E001"** (or type manually: set the
Employee ID field to `E001` and type *"I'm employee E001. Can I take 3 days of PTO next week?"*
into the message box, then click **Send**).

**SAY (while the response is loading):**
> "While this runs, the agent needs to do two things: look up this employee's actual PTO balance
> from our mock HR data, and retrieve the relevant policy text — specifically, how much advance
> notice is required for a multi-day leave request."

**DO:** Wait for the response. Once it appears, click to expand the **"Tool-call trace"** panel
under the assistant's reply.

**SAY:**
> "Here's the tool-call trace. You can see the agent called `check_pto_balance` with
> `employee_id: E001` — that's a real MCP tool call over stdio, not a hard-coded lookup — and it
> returned a balance of twelve point five days. Then it called `search_policy_documents` to
> retrieve the PTO policy's advance-notice rule."

**DO:** Collapse the trace panel, expand the **"Citations"** panel.

**SAY:**
> "And here are the citations: `POL-PTO-01`, section 3, which is the policy document ID and
> section the answer is grounded in, with the actual source snippet shown underneath. Notice the
> answer itself distinguishes a 'Policy fact' — the two-week advance notice rule, directly from
> the cited document — from a 'Recommendation' — my own suggested next step. That separation is a
> guardrail built into the system prompt, so the agent never states its own advice as if it were
> policy."

---

## 3:45–5:45 — Demo Task 2: Remote work eligibility (multi-document)

**SAY:**
> "Now the second required task: remote work eligibility, using employee E002. This one needs
> information from multiple policy documents, not just one."

**DO:** Click the quick-prompt chip labeled **"Remote work eligibility · E002"** (or type
manually: Employee ID `E002`, message *"I'm employee E002. I want to work from Indonesia for 6
weeks starting next month, is that allowed?"*).

**SAY (while loading):**
> "This time the agent should look up the employee's profile first — their role and FWA
> eligibility — and then pull together policy evidence specifically about overseas remote work."

**DO:** Once the response lands, expand the trace panel.

**SAY:**
> "The trace shows `lookup_employee_profile` first, then `check_policy_compliance` — that second
> tool bundles targeted policy evidence together with the employee's context in one call, which is
> why we only see two tool calls here instead of three or four."

**DO:** Expand the citations panel.

**SAY:**
> "And the citations span three different policy documents: `POL-FWA-03`, the remote work policy,
> for the overseas working-day caps and approval chain; `POL-SEC-05`, the data security policy,
> for VPN and access requirements while working abroad; and `POL-TRAVEL-14`, the business travel
> policy. That's the multi-document retrieval requirement satisfied in a single real task. The
> answer correctly concludes that six weeks exceeds the twenty-working-day annual overseas cap, so
> it needs a formal exception with Head of Department and People and Culture sign-off — grounded
> entirely in those cited sections, not invented."

---

## 5:45–6:45 — Safety guardrail: confirmation before a mock action

**SAY:**
> "Now let me show a safety guardrail. The system can create a mock HR ticket, but it should
> never do that without the user explicitly confirming first."

**DO:** Clear the Employee ID field, type `E003`, then type the message *"I'm employee E003.
Please open an HR ticket asking about my low PTO balance."* and send it.

**SAY (while loading):**
> "Watch what happens — the agent should preview the ticket, not create it yet."

**DO:** Once the response appears, read the on-screen answer aloud or paraphrase it, and expand
the trace panel to show the tool call.

**SAY:**
> "You can see in the trace that `create_mock_hr_ticket` was called with `confirmed: false` — and
> the tool itself refuses to write anything when that flag is false, it just returns a preview.
> The agent is asking me to confirm before going ahead."

**DO:** Type *"Yes, please go ahead and create it."* and send it.

**SAY (while loading):**
> "Now that I've confirmed, let's see the second call."

**DO:** Once the response appears, expand the trace panel again.

**SAY:**
> "Now `create_mock_hr_ticket` was called again, this time with `confirmed: true`, and a real
> mock ticket ID was returned. This two-step confirmation is enforced in the tool code itself, not
> just a prompt instruction — so even a confused or manipulated model literally cannot create a
> ticket without that explicit flag."

---

## 6:45–7:15 — Guardrail: out-of-scope refusal

**SAY:**
> "One more guardrail — the assistant should decline questions that have nothing to do with CPDA
> HR policy, instead of making something up."

**DO:** Type *"What is the capital of France?"* and send it.

**SAY (while loading, or once it returns):**
> "And here it declines, pointing me elsewhere, with an empty tool-call trace — zero wasted or
> hallucinated lookups."

---

## 7:15–8:00 — CI/CD walkthrough

**DO:** Switch to the GitHub repo's **Actions** tab.

**SAY:**
> "For CI/CD, every push to main triggers this GitHub Actions workflow: it installs dependencies,
> runs an import and build check, rebuilds the RAG index as an ingest smoke test, and then runs
> the full automated test suite — fifteen tests, including MCP tool discovery and a live MCP tool
> call, plus a live end-to-end agent test against Groq when the API key is available."

**DO:** Click into the most recent successful run, show the green checkmarks on the `test` job.

**SAY:**
> "Only after all of that passes does the second job run, which triggers an actual Render deploy
> hook — so deployment is gated on tests passing, not just on the push itself."

---

## 8:00–8:45 — Evaluation results walkthrough

**DO:** Navigate to `evaluation/results.md` in the repo file browser.

**SAY:**
> "For evaluation, I built a set of twenty-seven questions covering straightforward policy
> questions, multi-document questions, tool-requiring workflows, ambiguous requests, and
> out-of-scope requests, each with expected citations and expected tool calls. Running the full
> suite end to end against the live app gives a citation accuracy of ninety-four point seven
> percent, tool-selection accuracy of ninety percent, a hundred percent refusal accuracy on
> out-of-scope questions, and a hundred percent pass rate on the action-safety check we just
> demonstrated — the ticket confirmation flow."

**DO:** Scroll to the retrieval ablation section.

**SAY:**
> "I also ran a retrieval ablation comparing a top-k of three versus top-k of six — both hit a
> hundred percent retrieval accuracy on this corpus, which is why I settled on a default of five
> as a reasonable middle ground for multi-document questions. Latency and a documented Groq
> free-tier rate-limit constraint I ran into during testing are also written up here, along with
> how I mitigated it with retry and backoff logic."

---

## 8:45–9:00 — Close

**SAY:**
> "To summarize: a working agentic HR assistant combining policy RAG with real MCP tool calling
> over mock structured data, safety guardrails on irreversible actions and out-of-scope questions,
> a free-tier deployment on Render, a gated CI/CD pipeline, and a documented evaluation — all
> running end to end on the deployed URL. Thanks for watching."

**DO:** Stop recording.

---

## Quick reference: exact strings used in this script

| Step | Employee ID field | Message typed |
|---|---|---|
| Demo Task 1 | `E001` | `I'm employee E001. Can I take 3 days of PTO next week?` |
| Demo Task 2 | `E002` | `I'm employee E002. I want to work from Indonesia for 6 weeks starting next month, is that allowed?` |
| Guardrail (ticket, turn 1) | `E003` | `I'm employee E003. Please open an HR ticket asking about my low PTO balance.` |
| Guardrail (ticket, turn 2) | *(unchanged)* | `Yes, please go ahead and create it.` |
| Guardrail (refusal) | *(blank)* | `What's the capital of France?` |

All five can also be triggered by clicking the quick-prompt chips at the bottom of the chat card
(the first two are pre-wired to the exact Task 1 and Task 2 messages above).

## If something doesn't go to plan while recording

- **Slow response / spinner for a long time:** Groq's free tier can occasionally take 10–40+
  seconds per call under load, especially for the multi-tool Task 2. This is normal — keep talking
  through the architecture or guardrail explanation while it loads rather than cutting the clip.
- **"The LLM provider's free-tier rate limit was reached" error:** wait a minute or two and retry,
  or mention in voiceover that this is a known, documented free-tier constraint (see
  `evaluation/results.md`) and switch temporarily to running the app locally
  (`uvicorn app.main:app`) if you need to keep recording without a gap.
- **Status pill shows "Degraded":** hit `/health` directly in a new tab to see which check is
  failing (`mcp_connected`, `rag_index_ready`, or `groq_api_key_configured`), and mention it's
  likely a cold-start in progress — reload after a few seconds.
