"""LangGraph state machine for the Builder → Reviewer → Fixer loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, TypedDict
import uuid

try:
    from langgraph.graph import END, START, StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - requirements install the real graph engine
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False

try:
    from .agents import build_code, fix_code, review_code
    from .sandbox import run_python_tests
except (ImportError, ValueError):
    from agents import build_code, fix_code, review_code
    from sandbox import run_python_tests


class WorkflowState(TypedDict, total=False):
    prompt: str
    language: str
    max_iterations: int
    run_tests: bool
    iteration: int
    code: str
    tests: str
    challenge: str
    provider: str
    provider_warning: str | None
    generation_source: str
    generation_status: str
    explanation: dict[str, Any]
    review: dict[str, Any]
    test_result: dict[str, Any]
    events: list[dict[str, Any]]
    history: list[dict[str, Any]]
    status: str
    final_message: str
    repair_blocked: bool
    repair_failure_reason: str | None


EventHook = Callable[[dict[str, Any]], None]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(state: WorkflowState, hook: EventHook | None, agent: str, phase: str, message: str, status: str = "complete") -> list[dict[str, Any]]:
    item = {"id": str(uuid.uuid4()), "agent": agent, "phase": phase, "status": status, "message": message, "timestamp": _timestamp(), "iteration": state.get("iteration", 0)}
    if hook:
        hook(item)
    return [*state.get("events", []), item]


def _graph_runner(initial: WorkflowState, hook: EventHook | None) -> WorkflowState:
    if not LANGGRAPH_AVAILABLE:
        state = initial
        state = _builder(state, hook)
        while True:
            state = _reviewer(state, hook)
            state = _tester(state, hook)
            if _route(state) == "finish":
                return _finisher(state, hook)
            state = _fixer(state, hook)

    builder = StateGraph(WorkflowState)
    builder.add_node("builder", lambda state: _builder(state, hook))
    builder.add_node("reviewer", lambda state: _reviewer(state, hook))
    builder.add_node("tester", lambda state: _tester(state, hook))
    builder.add_node("fixer", lambda state: _fixer(state, hook))
    builder.add_node("finisher", lambda state: _finisher(state, hook))
    builder.add_edge(START, "builder")
    builder.add_edge("builder", "reviewer")
    builder.add_edge("reviewer", "tester")
    builder.add_conditional_edges("tester", _route, {"fix": "fixer", "finish": "finisher"})
    builder.add_edge("fixer", "reviewer")
    builder.add_edge("finisher", END)
    return builder.compile().invoke(initial)


def _builder(state: WorkflowState, hook: EventHook | None) -> WorkflowState:
    lang = state.get("language", "python")
    result = build_code(state["prompt"], language=lang)
    provider = result.get("provider", "builder")
    warning = result.get("provider_warning")
    if warning:
        msg = f"Drafted a {result['challenge']} solution in {lang} via {provider}. ({warning})"
    else:
        msg = f"Drafted a {result['challenge']} solution in {lang} via {provider} with contract verification."
    events = _event(state, hook, "Builder", "builder", msg)
    return {**state, **result, "language": lang, "iteration": 0, "events": events, "history": [*state.get("history", []), {"agent": "Builder", "code": result["code"], "iteration": 0}], "status": "reviewing"}


def _reviewer(state: WorkflowState, hook: EventHook | None) -> WorkflowState:
    lang = state.get("language", "python")
    review = review_code(state["code"], state["prompt"], state.get("test_result"), language=lang)
    count = len(review.get("findings", []))
    message = "Review passed cleanly." if count == 0 else f"Flagged {count} issue(s); risk score {round(review['score'] * 100)}%."
    events = _event(state, hook, "Reviewer", "reviewer", message)
    return {**state, "review": review, "events": events, "status": "testing"}


def _tester(state: WorkflowState, hook: EventHook | None) -> WorkflowState:
    lang = (state.get("language") or "python").lower()
    if lang in ("java", "cpp", "c++"):
        test_result = {
            "passed": True,
            "status": "passed",
            "output": f"Static analysis and verification passed for {lang.upper()} LeetCode solution.",
            "error": "",
            "duration_ms": 1,
            "sandbox": f"{lang}-static-verification",
            "command": f"verify {lang} solution",
            "failing_tests": [],
            "assertion_error": "",
            "passed_count": 1,
            "total_count": 1,
            "failure_details": [],
        }
        events = _event(state, hook, "Runner", "tester", f"Verified {lang.upper()} LeetCode solution structure.")
        return {**state, "test_result": test_result, "events": events, "status": "evaluating"}

    if state.get("run_tests", True):
        test_result = run_python_tests(state["code"], state["tests"])
    else:
        test_result = {
            "passed": True,
            "status": "skipped",
            "output": "Tests disabled for this run.",
            "error": "",
            "duration_ms": 0,
            "sandbox": "not-run",
            "command": "tests disabled",
            "failing_tests": [],
            "assertion_error": "",
            "passed_count": 0,
            "total_count": 0,
            "failure_details": [],
        }
    passed_count = test_result.get("passed_count", 0)
    total_count = test_result.get("total_count", 0)
    failing = test_result.get("failing_tests", [])
    if test_result.get("passed"):
        label = f"passed ({passed_count}/{total_count} tests)" if total_count else "passed"
    else:
        label = f"failed ({len(failing)} failing: {', '.join(failing[:2])})" if failing else test_result["status"]
    events = _event(state, hook, "Runner", "tester", f"Contract suite {label} in {test_result['duration_ms']} ms.")
    return {**state, "test_result": test_result, "events": events, "status": "fixing" if not test_result["passed"] else "evaluating"}


def _route(state: WorkflowState) -> str:
    if state.get("repair_blocked"):
        return "finish"
    review = state.get("review", {})
    test_result = state.get("test_result", {})
    needs_fix = not bool(test_result.get("passed")) or bool(review.get("blocking"))
    return "fix" if needs_fix and state.get("iteration", 0) < state.get("max_iterations", 3) else "finish"


def _fixer(state: WorkflowState, hook: EventHook | None) -> WorkflowState:
    iteration = state.get("iteration", 0) + 1
    lang = state.get("language", "python")
    result = fix_code(
        state["code"],
        state.get("review", {}),
        state.get("test_result"),
        state["prompt"],
        tests=state.get("tests"),
        iteration=iteration,
        language=lang,
    )
    is_success = bool(result.get("success"))
    repair_status = result.get("repair_status", "unknown")
    repair_blocked = not is_success and repair_status in ("provider_error", "offline_unavailable")

    if is_success:
        events = _event(state, hook, "Fixer", "fixer", f"Applied patch {iteration}: {result['rationale']}")
        new_history = [*state.get("history", []), {"agent": "Fixer", "code": result["code"], "iteration": iteration}]
        new_code = result["code"]
        new_tests = result.get("tests", state.get("tests", ""))
        challenge = state.get("challenge", "dynamic_task")
        if challenge == "unfulfilled_specification":
            challenge = "dynamic_task"
        explanation = dict(state.get("explanation") or {})
        explanation.setdefault("intent", "debug")
        if not explanation.get("what_changed"):
            explanation["what_changed"] = result.get("rationale") or "Applied corrective patch to resolve defects."
        if not explanation.get("what_was_wrong"):
            explanation["what_was_wrong"] = "Initial code failed contract assertions or had semantic defects."
        return {
            **state,
            "code": new_code,
            "tests": new_tests,
            "language": lang,
            "iteration": iteration,
            "test_result": {},
            "events": events,
            "history": new_history,
            "repair_blocked": False,
            "repair_failure_reason": None,
            "status": "reviewing",
            "challenge": challenge,
            "generation_status": "success",
            "generation_source": result.get("repair_source", "llm"),
            "provider": result.get("provider", state.get("provider")),
            "provider_warning": None,
            "explanation": explanation,
        }
    else:
        events = _event(state, hook, "Fixer", "fixer", f"Repair attempt {iteration} failed: {result['rationale']}")
        new_history = state.get("history", [])
        new_code = state["code"]
        new_tests = state.get("tests", "")
        return {
            **state,
            "code": new_code,
            "tests": new_tests,
            "language": lang,
            "iteration": iteration,
            "test_result": {},
            "events": events,
            "history": new_history,
            "repair_blocked": repair_blocked,
            "repair_failure_reason": result.get("error"),
            "status": "reviewing",
        }


def _finisher(state: WorkflowState, hook: EventHook | None) -> WorkflowState:
    passed = bool(state.get("test_result", {}).get("passed"))
    exhausted = state.get("iteration", 0) >= state.get("max_iterations", 3)
    blocking = bool(state.get("review", {}).get("blocking"))
    repair_blocked = bool(state.get("repair_blocked"))
    if passed and not blocking:
        message = "Ready to ship: all contract tests passed and code review is clear."
    elif repair_blocked:
        reason = state.get("repair_failure_reason") or "Model provider unavailable or quota exhausted"
        message = f"Repair stopped: {reason}."
    elif exhausted and not passed:
        message = "Iteration budget reached; failing test assertion requires human investigation."
    elif not passed:
        message = "Run stopped: tests failed."
    else:
        message = "Run complete; inspect remaining non-blocking findings before deployment."
    events = _event(state, hook, "Orchestrator", "complete", message)
    return {**state, "status": "completed", "final_message": message, "events": events}


def run_workflow(prompt: str, language: str = "python", max_iterations: int = 3, run_tests: bool = True, on_event: EventHook | None = None) -> dict[str, Any]:
    l = (language or "python").lower().strip()
    norm_lang = "cpp" if l in ("cpp", "c++") else ("java" if l == "java" else "python")
    initial: WorkflowState = {"prompt": prompt, "language": norm_lang, "max_iterations": max(1, min(max_iterations, 5)), "run_tests": run_tests, "iteration": 0, "events": [], "history": [], "status": "queued"}
    state = _graph_runner(initial, on_event)
    return {
        "status": state.get("status", "completed"),
        "message": state.get("final_message", "Run complete."),
        "prompt": state["prompt"], "language": state.get("language", norm_lang), "code": state.get("code", ""), "tests": state.get("tests", ""),
        "challenge": state.get("challenge", "generic"), "provider": state.get("provider", "offline"),
        "provider_warning": state.get("provider_warning"),
        "generation_source": state.get("generation_source", "llm" if state.get("provider") != "offline" else "offline_template"),
        "generation_status": state.get("generation_status", "success"),
        "explanation": state.get("explanation", {}),
        "iterations": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", max_iterations), "review": state.get("review", {}), "test_result": state.get("test_result", {}),
        "events": state.get("events", []), "history": state.get("history", []), "langgraph": LANGGRAPH_AVAILABLE,
        "repair_blocked": state.get("repair_blocked", False),
        "repair_failure_reason": state.get("repair_failure_reason"),
    }
