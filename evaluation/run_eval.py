"""Evaluation runner for the CPDA HR Agentic RAG application.

Usage:
    # 1. Start the app locally (needs GROQ_API_KEY):
    uvicorn app.main:app --host 127.0.0.1 --port 8000
    # 2. In another terminal:
    python evaluation/run_eval.py --base-url http://127.0.0.1:8000

Reads evaluation/eval_questions.jsonl, sends each question to /chat, scores answer-quality and
agent-behavior metrics heuristically (documented below), and writes a raw JSON dump plus a
retrieval-k ablation report. Results are then written up in evaluation/results.md.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVAL_DIR / "eval_questions.jsonl"
OUTPUT_PATH = EVAL_DIR / "eval_run_output.json"

REFUSAL_MARKERS = [
    "don't have", "do not have", "not in the", "not available in", "cpda policy corpus",
    "outside the scope", "can't help with that", "unable to answer", "not something i can",
]
CLARIFICATION_MARKERS = ["?", "could you", "can you confirm", "which employee", "let me know your"]


def load_questions() -> list[dict]:
    questions = []
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def call_chat(client: httpx.Client, base_url: str, message: str) -> tuple[dict, float]:
    start = time.time()
    resp = client.post(f"{base_url}/chat", json={"message": message}, timeout=120.0)
    elapsed_ms = (time.time() - start) * 1000
    resp.raise_for_status()
    return resp.json(), elapsed_ms


def _normalize(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'").lower()


def score_question(q: dict, response: dict) -> dict:
    answer_lower = _normalize(response["answer"])
    trace_tools = [step["tool"] for step in response["trace"]]
    cited_doc_ids = {c["doc_id"] for c in response["citations"]}

    scores: dict = {}

    if q["expected_doc_ids"]:
        overlap = len(set(q["expected_doc_ids"]) & cited_doc_ids)
        scores["citation_accuracy"] = overlap / len(q["expected_doc_ids"])
    else:
        scores["citation_accuracy"] = None

    if q["gold_keywords"]:
        hits = sum(1 for kw in q["gold_keywords"] if kw.lower() in answer_lower)
        scores["groundedness_keyword_match"] = hits / len(q["gold_keywords"])
    else:
        scores["groundedness_keyword_match"] = None

    if q["expected_tools"]:
        overlap = len(set(q["expected_tools"]) & set(trace_tools))
        scores["tool_selection_accuracy"] = overlap / len(q["expected_tools"])
    else:
        scores["tool_selection_accuracy"] = None

    if q["category"] == "tool_workflow":
        scores["workflow_completed"] = bool(response["answer"]) and (
            scores["tool_selection_accuracy"] is None or scores["tool_selection_accuracy"] > 0
        )
    else:
        scores["workflow_completed"] = None

    if q.get("expect_clarification"):
        asked_clarifying = any(m in answer_lower for m in CLARIFICATION_MARKERS)
        avoided_guessing = len(trace_tools) == 0
        scores["clarification_correct"] = asked_clarifying and avoided_guessing
    else:
        scores["clarification_correct"] = None

    if q.get("expect_refusal"):
        scores["refusal_correct"] = any(m in answer_lower for m in REFUSAL_MARKERS) and len(trace_tools) == 0
    else:
        scores["refusal_correct"] = None

    if q.get("expect_confirmation_prompt"):
        ticket_calls = [s for s in response["trace"] if s["tool"] == "create_mock_hr_ticket"]
        not_auto_confirmed = all(not s["arguments"].get("confirmed") for s in ticket_calls)
        asked = any(m in answer_lower for m in ["shall i", "confirm", "go ahead", "would you like"])
        scores["action_safety_pass"] = not_auto_confirmed and asked
    else:
        scores["action_safety_pass"] = None

    return scores


def aggregate(results: list[dict]) -> dict:
    def avg(key: str) -> float | None:
        vals = [r["scores"][key] for r in results if r["scores"].get(key) is not None]
        return round(statistics.mean(vals), 3) if vals else None

    def rate(key: str) -> float | None:
        vals = [r["scores"][key] for r in results if r["scores"].get(key) is not None]
        return round(sum(1 for v in vals if v) / len(vals), 3) if vals else None

    latencies = [r["latency_ms"] for r in results]
    latencies_sorted = sorted(latencies)

    def percentile(p: float) -> float:
        if not latencies_sorted:
            return 0.0
        idx = min(int(len(latencies_sorted) * p), len(latencies_sorted) - 1)
        return round(latencies_sorted[idx], 1)

    return {
        "n_questions": len(results),
        "citation_accuracy_avg": avg("citation_accuracy"),
        "groundedness_keyword_match_avg": avg("groundedness_keyword_match"),
        "tool_selection_accuracy_avg": avg("tool_selection_accuracy"),
        "workflow_completion_rate": rate("workflow_completed"),
        "clarification_accuracy": rate("clarification_correct"),
        "refusal_accuracy": rate("refusal_correct"),
        "action_safety_pass_rate": rate("action_safety_pass"),
        "latency_ms_p50": percentile(0.50),
        "latency_ms_p95": percentile(0.95),
        "latency_ms_mean": round(statistics.mean(latencies), 1) if latencies else 0,
    }


def run_retrieval_k_ablation(base_url: str) -> dict:
    """Ablation: retrieval top_k=3 vs top_k=6, measured as doc-hit-rate directly against the
    retriever (bypasses the LLM so it is fast, cheap, and isolates the retrieval component)."""
    sys.path.insert(0, str(EVAL_DIR.parent))
    from app.rag.retriever import retrieve  # noqa: E402

    questions = [q for q in load_questions() if q["expected_doc_ids"]]
    report = {}
    for k in (3, 6):
        hits = 0
        for q in questions:
            results = retrieve(q["question"], top_k=k)
            found_doc_ids = {r.doc_id for r in results}
            if set(q["expected_doc_ids"]) & found_doc_ids:
                hits += 1
        report[f"top_k={k}"] = {"hit_rate": round(hits / len(questions), 3), "n": len(questions)}
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    questions = load_questions()
    results = []

    with httpx.Client() as client:
        for q in questions:
            print(f"[{q['id']}] {q['question'][:70]}...")
            try:
                response, latency_ms = call_chat(client, args.base_url, q["question"])
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR: {exc}")
                results.append({"id": q["id"], "category": q["category"], "error": str(exc)})
                continue
            scores = score_question(q, response)
            results.append(
                {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "answer": response["answer"],
                    "trace_tools": [s["tool"] for s in response["trace"]],
                    "citations": [c["doc_id"] for c in response["citations"]],
                    "latency_ms": round(latency_ms, 1),
                    "scores": scores,
                }
            )

    summary = aggregate([r for r in results if "scores" in r])
    ablation = run_retrieval_k_ablation(args.base_url)

    output = {"summary": summary, "ablation_retrieval_k": ablation, "results": results}
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("\n=== ABLATION (retrieval top_k) ===")
    print(json.dumps(ablation, indent=2))
    print(f"\nFull results written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
