# Deployment Info

> **TODO (submitter):** fill in the two URLs below after deploying to Render (or an equivalent
> free-tier host), then remove this notice.

- **Deployed application URL:** `https://<your-service-name>.onrender.com` *(replace with your
  actual Render URL)*
- **Health endpoint:** `https://<your-service-name>.onrender.com/health`

## How this was deployed

Single Render free-tier Web Service, per `render.yaml`:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `python -m app.rag.ingest && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/health`
- **Environment variables set in the Render dashboard:**
  - `GROQ_API_KEY` — required, your own free key from console.groq.com (marked `sync: false` in
    `render.yaml` so Render prompts for it rather than storing it in the repo).
  - `GROQ_MODEL` — defaults to `openai/gpt-oss-120b` (set in `render.yaml`); change if your Groq
    account has access to a different tool-calling-capable model.
  - The remaining variables (`CHROMA_PERSIST_DIR`, `CORPUS_DIR`, `MOCK_DATA_DIR`,
    `RETRIEVAL_TOP_K`, `AGENT_MAX_TOOL_ITERATIONS`, `MCP_SERVER_CMD`) are pre-filled in
    `render.yaml` with sensible defaults and don't need to be changed for the default setup.

### Steps to deploy (Render dashboard)

1. Push this repository to GitHub (see main `README.md`).
2. In Render: **New +** → **Blueprint** → connect the GitHub repo → Render reads `render.yaml`
   and proposes the `cpda-hr-assistant` web service.
3. When prompted, paste in your `GROQ_API_KEY`.
4. Deploy. First build installs dependencies and runs the RAG ingest step (downloads the small
   local ONNX embedding model on first run, then builds the Chroma index from `corpus/`).

### CI-triggered redeploys (optional)

`.github/workflows/ci.yml` has a `deploy` job that, after tests pass on a push to `main`, will
`curl` a Render **Deploy Hook** URL if you add it as a repository secret named
`RENDER_DEPLOY_HOOK_URL` (Render dashboard → your service → Settings → Deploy Hook). Without that
secret, the job just logs a message and does nothing — Render's own GitHub integration (step 2
above) already auto-deploys on push by default, so this is only needed if you've disabled that
and want the deploy to be explicitly gated on the GitHub Actions test job.

## Free-tier cold start behavior

Render's free tier spins the service down after a period of inactivity. On the next request:

- The container restarts, dependencies are already installed (cached image), but the **start
  command re-runs `python -m app.rag.ingest`**, which rebuilds the Chroma index from the
  committed `corpus/` files. This typically takes a few seconds to ~30s depending on whether the
  local embedding model needs to be re-downloaded (it's cached in the image layer after the
  first build in most cases, but a fresh instance may re-fetch it).
- The very first chat request after a cold start will also pay for MCP subprocess startup and
  the first Groq API call's connection setup.
- **Practical guidance:** expect the first request after idling to take noticeably longer
  (several seconds to under a minute) than subsequent "warm" requests, which typically complete
  in a few seconds. If demoing right after a period of inactivity, hit `/health` first to warm
  the instance before starting the recorded walkthrough.

## Local-only fallback

If the free-tier deployment is temporarily unavailable when this is graded, the entire system
also runs locally with no code changes — see `README.md` → "Running locally". This satisfies the
assignment's requirement that "the agentic system must also run locally for development."
