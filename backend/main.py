"""FastAPI service for the BobBuilders multi-agent coding assistant."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import threading
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .model_client import get_active_provider_info
    from .workflow import run_workflow
except (ImportError, ValueError):
    from model_client import get_active_provider_info
    from workflow import run_workflow


class RunRequest(BaseModel):
    prompt: str = Field(default="", max_length=50000)
    language: str = Field(default="python")
    max_iterations: int = Field(default=3, ge=1, le=5)
    run_tests: bool = True
    images: list[str] = Field(default_factory=list)


class RunRecord(dict[str, Any]):
    pass


app = FastAPI(title="BobForge LeetCode Assistant", version="2.0.0", description="Intelligent LeetCode problem solving, debugging, and optimization assistant.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
RUNS: dict[str, RunRecord] = {}
RUNS_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_lang(language: str | None) -> str:
    l = (language or "python").lower().strip()
    if l in ("cpp", "c++"):
        return "cpp"
    if l == "java":
        return "java"
    return "python"


def _event_hook(run_id: str, event: dict[str, Any]) -> None:
    with RUNS_LOCK:
        record = RUNS.get(run_id)
        if record:
            record["phase"] = event.get("phase", "working")
            record["events"] = [*record.get("events", []), event]
            record["updated_at"] = _now()


async def _execute(run_id: str, request: RunRequest) -> None:
    norm_lang = _normalize_lang(request.language)
    try:
        with RUNS_LOCK:
            RUNS[run_id]["status"] = "running"
            RUNS[run_id]["phase"] = "builder"
            RUNS[run_id]["updated_at"] = _now()
        result = await asyncio.to_thread(
            run_workflow,
            request.prompt,
            norm_lang,
            request.max_iterations,
            request.run_tests,
            lambda event: _event_hook(run_id, event),
            request.images,
        )
        with RUNS_LOCK:
            RUNS[run_id].update({"status": "completed", "phase": "complete", "result": result, "events": result.get("events", RUNS[run_id].get("events", [])), "updated_at": _now()})
    except Exception as exc:  # pragma: no cover - defensive API boundary
        with RUNS_LOCK:
            RUNS[run_id].update({"status": "error", "phase": "error", "error": str(exc), "updated_at": _now()})


@app.get("/api/health")
async def health() -> dict[str, Any]:
    provider_info = get_active_provider_info()
    return {
        "ok": True,
        "service": "bobforge-api",
        "provider": provider_info.get("active", {}),
        "configured_providers": provider_info.get("configured_providers", []),
        "mode": provider_info.get("mode", "offline"),
    }


@app.get("/api/templates")
async def templates() -> dict[str, Any]:
    return {"templates": [
        {"id": "two_sum", "label": "Two Sum (Solve)", "prompt": "LeetCode 1: Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target. Implement using class Solution with optimal O(n) time complexity.", "accent": "cyan"},
        {"id": "valid_parentheses_debug", "label": "Valid Parentheses (Debug)", "prompt": "Problem: LeetCode 20 Valid Parentheses. Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nMy code:\nclass Solution:\n    def isValid(self, s: str) -> bool:\n        stack = []\n        for c in s:\n            if c in '({[':\n                stack.append(c)\n            else:\n                if not stack or stack.pop() != c:\n                    return False\n        return True\n\nQuestion: Why does my code fail on valid inputs like '()'? What did I do wrong?", "accent": "orange"},
        {"id": "lru_cache_opt", "label": "LRU Cache (Optimize)", "prompt": "LeetCode 146: Implement a Least Recently Used (LRU) Cache with O(1) time complexity for both get and put operations using class LRUCache.", "accent": "violet"},
        {"id": "binary_search_explain", "label": "Binary Search (Explain)", "prompt": "LeetCode 704: Given an array of integers nums which is sorted in ascending order, and an integer target, write a function to search target in nums. If target exists, return its index. Otherwise, return -1. Must be O(log n) runtime complexity.", "accent": "cyan"},
        {"id": "fibonacci", "label": "Fibonacci contract", "prompt": "Build a function that returns the nth Fibonacci number. Handle n=0 and n=1, reject negative values, and validate types.", "accent": "violet"},
        {"id": "prime", "label": "Prime checker", "prompt": "Build a utility that checks whether an integer is prime, validates input, and includes tests for edge cases.", "accent": "cyan"},
        {"id": "palindrome", "label": "Palindrome parser", "prompt": "Build a palindrome checker that ignores punctuation and casing, validates strings, and includes tests.", "accent": "orange"},
        {"id": "lru_cache", "label": "LRU Cache", "prompt": "Implement a Least Recently Used (LRU) Cache with O(1) get and put operations, fixed capacity eviction, and boundary test assertions.", "accent": "cyan"},
        {"id": "rate_limiter", "label": "Rate Limiter", "prompt": "Build a Token Bucket Rate Limiter supporting capacity limits, timestamp-based refills, and request acceptance validations.", "accent": "violet"},
        {"id": "binary_search", "label": "Binary Search", "prompt": "Implement a binary search algorithm for sorted lists returning the target element index or -1 with boundary tests.", "accent": "cyan"},
        {"id": "dijkstra", "label": "Dijkstra Shortest Path", "prompt": "Build Dijkstra's shortest path algorithm for weighted directed graphs using a min-heap priority queue with edge validation.", "accent": "orange"},
        {"id": "email_validator", "label": "Email Validator", "prompt": "Build an RFC-standard email validator with syntax regex, domain validation, length limits, and edge case tests.", "accent": "violet"},
    ]}


@app.post("/api/runs", status_code=202)
async def create_run(request: RunRequest) -> dict[str, Any]:
    effective_prompt = request.prompt.strip()
    if not effective_prompt and not request.images:
        raise HTTPException(
            status_code=422,
            detail="Please provide a problem prompt, your code/error, or attach an image/screenshot.",
        )
    if not effective_prompt:
        effective_prompt = "Please analyze the attached image/screenshot (LeetCode problem, code, or error message) and provide the correct solution, explanation, and error diagnosis."
    request.prompt = effective_prompt

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    now = _now()
    norm_lang = _normalize_lang(request.language)
    with RUNS_LOCK:
        RUNS[run_id] = RunRecord({
            "id": run_id,
            "status": "queued",
            "phase": "queued",
            "prompt": effective_prompt,
            "language": norm_lang,
            "images": request.images,
            "created_at": now,
            "updated_at": now,
            "events": [],
        })
    asyncio.create_task(_execute(run_id, request))
    return {"id": run_id, "status": "queued"}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    with RUNS_LOCK:
        record = RUNS.get(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return dict(record)

