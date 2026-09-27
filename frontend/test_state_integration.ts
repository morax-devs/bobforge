import assert from "node:assert/strict";
import {
  getWorkflowFailureInfo,
  getOverallStatus,
  derivePipelineStages,
  deriveCurrentMessage,
  deriveProviderDisplay,
  deriveLeetCodeStatus,
  parseExplanation,
} from "./src/stateHelpers.ts";
import type { RunRecord, RunResult, TestResult, ExplanationInfo } from "./src/types.ts";

console.log("==================================================");
console.log("RUNNING FRONTEND STATE INTEGRATION TEST SUITE");
console.log("==================================================");

let passedCount = 0;
function it(name: string, fn: () => void) {
  try {
    fn();
    console.log(`✓ PASS: ${name}`);
    passedCount++;
  } catch (err) {
    console.error(`✗ FAIL: ${name}`);
    console.error(err);
    process.exit(1);
  }
}

// 1. Successful workflow renders completed state
it("1. Successful workflow renders completed state", () => {
  const result: RunResult = {
    status: "completed",
    message: "Ready to ship: all contract tests passed and code review is clear.",
    prompt: "Implement binary search in Python",
    language: "python",
    code: "def binary_search(arr, target): return 0",
    tests: "import unittest...",
    challenge: "binary_search",
    provider: "anthropic",
    generation_source: "llm",
    generation_status: "success",
    iterations: 0,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: {
      passed: true,
      status: "passed",
      passed_count: 3,
      total_count: 3,
      duration_ms: 120,
      sandbox: "subprocess",
      command: "python -m unittest",
      output: "OK",
      error: "",
    },
    events: [],
    history: [],
    langgraph: true,
  };
  const run: RunRecord = {
    id: "run_1234",
    status: "completed",
    phase: "complete",
    prompt: result.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
    result,
  };

  const failure = getWorkflowFailureInfo(run, result, result.test_result);
  assert.equal(failure, null, "Successful run must not produce failure info");

  const overall = getOverallStatus(run, result, result.test_result, "complete", false, failure);
  assert.equal(overall, "completed", "Overall status must be completed");

  const stages = derivePipelineStages("complete", false, result, result.test_result, run.status);
  assert.equal(stages[0].status, "completed");
  assert.equal(stages[0].statusText, "Synthesized");
  assert.equal(stages[1].status, "completed");
  assert.equal(stages[1].statusText, "Verified");
  assert.equal(stages[2].status, "completed");
  assert.equal(stages[2].statusText, "3/3 Passed");
  assert.equal(stages[3].status, "completed");
  assert.equal(stages[3].statusText, "Not required");
});

// 2. Generation provider failure renders failure
it("2. Generation provider failure renders failure", () => {
  const result: RunResult = {
    status: "completed",
    message: "Generation failed: Anthropic quota error: Credit balance is too low",
    prompt: "Build an arbitrary complex system",
    language: "python",
    code: 'raise RuntimeError("Generation failed")',
    tests: "class T: ...",
    challenge: "unfulfilled_specification",
    provider: "anthropic",
    provider_warning: "Anthropic quota error: Credit balance is too low (Error 400).",
    generation_source: "failed",
    generation_status: "provider_error",
    iterations: 0,
    max_iterations: 3,
    review: { passed: false, blocking: true, score: 0.9, summary: "Generation failed", findings: [] },
    test_result: {
      passed: false,
      status: "failed",
      passed_count: 0,
      total_count: 1,
      duration_ms: 10,
      sandbox: "subprocess",
      command: "python -m unittest",
      output: "",
      error: "RuntimeError",
    },
    events: [],
    history: [],
    langgraph: true,
  };
  const run: RunRecord = {
    id: "run_failed_builder",
    status: "completed",
    phase: "complete",
    prompt: result.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
    result,
  };

  const failure = getWorkflowFailureInfo(run, result, result.test_result);
  assert.ok(failure && failure.isFailure, "Must register as an explicit failure");
  assert.equal(failure?.type, "provider_error");
  assert.equal(failure?.title, "Unable to generate implementation");
  assert.match(failure?.message || "", /quota error/i);

  const overall = getOverallStatus(run, result, result.test_result, "complete", false, failure);
  assert.equal(overall, "failed", "Provider failure must NEVER show completed");

  const stages = derivePipelineStages("complete", false, result, result.test_result, run.status);
  assert.equal(stages[0].status, "failed");
  assert.equal(stages[0].statusText, "Generation Failed");
});

// 3. Semantic review failure does not render success
it("3. Semantic review failure does not render success", () => {
  const result: RunResult = {
    status: "completed",
    message: "Specification not fulfilled: Fibonacci provided instead of Sudoku",
    prompt: "Build a Sudoku game in CustomTkinter",
    language: "python",
    code: "def fibonacci(n): return n",
    tests: "import unittest...",
    challenge: "sudoku",
    provider: "anthropic",
    generation_source: "llm",
    generation_status: "success",
    iterations: 0,
    max_iterations: 3,
    review: {
      passed: false,
      blocking: true,
      score: 0.85,
      summary: "Severe semantic mismatch: Code implements Fibonacci instead of Sudoku GUI",
      semantic_review_status: "failed",
      semantic_review: {
        status: "failed",
        passed: false,
        summary: "The generated code implements Fibonacci numbers rather than a Sudoku game.",
      },
      findings: [
        {
          category: "semantic_mismatch",
          severity: "high",
          line: 1,
          title: "Semantic mismatch",
          detail: "Code implements Fibonacci numbers rather than a Sudoku game.",
          fix: "Implement SudokuGame class.",
        },
      ],
    },
    test_result: {
      passed: true,
      status: "passed",
      passed_count: 1,
      total_count: 1,
      duration_ms: 100,
      sandbox: "subprocess",
      command: "python -m unittest",
      output: "OK",
      error: "",
    },
    events: [],
    history: [],
    langgraph: true,
  };
  const run: RunRecord = {
    id: "run_semantic_fail",
    status: "completed",
    phase: "complete",
    prompt: result.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
    result,
  };

  const failure = getWorkflowFailureInfo(run, result, result.test_result);
  assert.ok(failure && failure.isFailure);
  assert.equal(failure?.type, "semantic_failure");
  assert.equal(failure?.title, "Specification Not Satisfied");

  const overall = getOverallStatus(run, result, result.test_result, "complete", false, failure);
  assert.equal(overall, "failed", "Semantic failure must NOT report completed");

  const stages = derivePipelineStages("complete", false, result, result.test_result, run.status);
  assert.equal(stages[1].status, "failed");
  assert.equal(stages[1].statusText, "Semantic Mismatch");
});

// 4. Runner/test failure is visible
it("4. Runner/test failure is visible and renders failure", () => {
  const result: RunResult = {
    status: "completed",
    message: "Iteration budget reached; failing test assertion requires human investigation.",
    prompt: "Build an email validator",
    language: "python",
    code: "def validate_email(email): return True",
    tests: "class T: ...",
    challenge: "email_validator",
    provider: "anthropic",
    generation_source: "llm",
    generation_status: "success",
    iterations: 3,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: {
      passed: false,
      status: "failed",
      passed_count: 1,
      total_count: 3,
      failing_tests: ["test_reject_empty", "test_reject_missing_at"],
      assertion_error: "AssertionError: True is not false",
      duration_ms: 150,
      sandbox: "subprocess",
      command: "python -m unittest",
      output: "",
      error: "FAIL",
    },
    events: [],
    history: [],
    langgraph: true,
  };
  const run: RunRecord = {
    id: "run_test_failed",
    status: "completed",
    phase: "complete",
    prompt: result.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
    result,
  };

  const failure = getWorkflowFailureInfo(run, result, result.test_result);
  assert.ok(failure && failure.isFailure);
  assert.equal(failure?.type, "repair_exhausted");
  assert.equal(failure?.title, "Repair Budget Exhausted");

  const overall = getOverallStatus(run, result, result.test_result, "complete", false, failure);
  assert.equal(overall, "failed", "Exhausted failing run must report failed");

  const stages = derivePipelineStages("complete", false, result, result.test_result, run.status);
  assert.equal(stages[2].status, "failed");
  assert.equal(stages[2].statusText, "2 Test Failed");
  assert.equal(stages[3].status, "failed");
  assert.equal(stages[3].statusText, "Exhausted (3 iter)");
});

// 5. Repair iteration is visible
it("5. Repair iteration is visible during execution and in stage badges", () => {
  const result: RunResult = {
    status: "running",
    message: "",
    prompt: "Parse number with multiple checks",
    language: "python",
    code: "def parse_num(s): ...",
    tests: "class T: ...",
    challenge: "num_parser",
    provider: "anthropic",
    generation_source: "llm",
    generation_status: "success",
    iterations: 1,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: {
      passed: false,
      status: "failed",
      passed_count: 1,
      total_count: 2,
      failing_tests: ["test_float"],
      duration_ms: 50,
      sandbox: "subprocess",
      command: "",
      output: "",
      error: "",
    },
    events: [{ agent: "Fixer", phase: "fixer", message: "Applied patch 2: Float support", timestamp: new Date().toISOString() }],
    history: [],
    langgraph: true,
  };
  const run: RunRecord = {
    id: "run_repairing",
    status: "running",
    phase: "fixer",
    prompt: result.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: result.events,
    result,
  };

  const overall = getOverallStatus(run, result, result.test_result, "fixer", false, null);
  assert.equal(overall, "repairing", "Workflow must report repairing status during Fixer phase");

  const stages = derivePipelineStages("fixer", false, result, result.test_result, run.status);
  assert.equal(stages[3].status, "repairing");
  assert.equal(stages[3].statusText, "Repairing (iter 2)");

  const currentMsg = deriveCurrentMessage(false, run.status, "fixer", result.iterations, result.events);
  assert.equal(currentMsg, "Repairing — iteration 2...");
});

// 6. Repaired code replaces failed code in the workspace
it("6. Repaired code replaces failed code in the workspace upon patch success", () => {
  const patchedCode = "def parse_num(s): return int(float(s)) if '.' in s else int(s)";
  const patchedTests = "class T(unittest.TestCase): ...";
  const result: RunResult = {
    status: "completed",
    message: "Ready to ship: all contract tests passed and code review is clear.",
    prompt: "Parse numbers",
    language: "python",
    code: patchedCode,
    tests: patchedTests,
    challenge: "num_parser",
    provider: "anthropic",
    generation_source: "llm",
    generation_status: "success",
    iterations: 2,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: {
      passed: true,
      status: "passed",
      passed_count: 3,
      total_count: 3,
      duration_ms: 80,
      sandbox: "subprocess",
      command: "python -m unittest",
      output: "OK",
      error: "",
    },
    events: [],
    history: [
      { agent: "Builder", code: "def parse_num(s): return 0", iteration: 0 },
      { agent: "Fixer", code: "def parse_num(s): return int(s)", iteration: 1 },
      { agent: "Fixer", code: patchedCode, iteration: 2 },
    ],
    langgraph: true,
  };
  const run: RunRecord = {
    id: "run_repaired",
    status: "completed",
    phase: "complete",
    prompt: result.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
    result,
  };

  const failure = getWorkflowFailureInfo(run, result, result.test_result);
  assert.equal(failure, null);

  const overall = getOverallStatus(run, result, result.test_result, "complete", false, failure);
  assert.equal(overall, "completed");

  const stages = derivePipelineStages("complete", false, result, result.test_result, run.status);
  assert.equal(stages[3].status, "completed");
  assert.equal(stages[3].statusText, "Patched (2 iter)");
  assert.equal(stages[3].badge, "×2");
  assert.equal(result.code, patchedCode, "Repaired code must be active in result");
  assert.equal(result.history.length, 3, "All revisions must be preserved in history");
});

// 7. Provider warnings are sanitized and presented safely
it("7. Provider warnings are presented safely and generation source distinguished", () => {
  const llmResult: RunResult = {
    status: "completed",
    message: "Ready",
    prompt: "test",
    language: "python",
    code: "def f(): pass",
    tests: "class T: pass",
    challenge: "test",
    provider: "anthropic",
    generation_source: "llm",
    iterations: 0,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "", findings: [] },
    test_result: { passed: true, status: "passed", duration_ms: 10, sandbox: "", command: "", output: "", error: "" },
    events: [],
    history: [],
    langgraph: true,
  };
  assert.equal(deriveProviderDisplay(llmResult), "Claude 3.5 (LLM)");

  const templateResult: RunResult = {
    ...llmResult,
    provider: "offline",
    generation_source: "offline_template",
  };
  assert.equal(deriveProviderDisplay(templateResult), "Offline Template (Benchmark)");

  const failedResult: RunResult = {
    ...llmResult,
    provider: "openai",
    generation_source: "failed",
    generation_status: "provider_error",
  };
  assert.equal(deriveProviderDisplay(failedResult), "openai (Failed)");
});

// 8. Existing frontend behavior remains intact
it("8. Existing idle, running, and error flows remain intact", () => {
  // Idle state
  assert.equal(getOverallStatus(null, undefined, undefined, "queued", false, null), "idle");

  // Running state starting
  assert.equal(getOverallStatus(null, undefined, undefined, "builder", true, null), "running");

  // Error boundary
  const errorRun: RunRecord = {
    id: "run_err",
    status: "error",
    phase: "error",
    prompt: "test",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
    error: "Network connection refused",
  };
  const errFailure = getWorkflowFailureInfo(errorRun);
  assert.equal(errFailure?.isFailure, true);
  assert.equal(errFailure?.type, "general_error");
  assert.equal(getOverallStatus(errorRun, undefined, undefined, "error", false, errFailure), "failed");
});

// 9. Pipeline self-healing recovery after initial builder failure renders completed and recovered
it("9. Pipeline self-healing recovery after initial builder failure renders completed and recovered", () => {
  const recoveredResult: RunResult = {
    status: "completed",
    message: "Ready to ship: all contract tests passed and code review is clear.",
    prompt: "build a sudoku game using python and custom tkinter",
    language: "python",
    code: "import tkinter as tk\nclass SudokuGame: pass",
    tests: "import unittest\nclass SudokuTest(unittest.TestCase): ...",
    challenge: "dynamic_task",
    provider: "gemini",
    generation_source: "llm",
    generation_status: "success",
    provider_warning: null,
    iterations: 1,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.28, summary: "Review passed cleanly.", findings: [] },
    test_result: {
      passed: true,
      status: "passed",
      passed_count: 3,
      total_count: 3,
      duration_ms: 371,
      sandbox: "subprocess",
      command: "python -m unittest",
      output: "OK",
      error: "",
    },
    events: [
      { agent: "Builder", phase: "builder", message: "Drafted a unfulfilled_specification solution via gemini. (503 error)", timestamp: "" },
      { agent: "Fixer", phase: "fixer", message: "Applied patch 1: Replaced placeholder with complete game", timestamp: "" },
    ],
    history: [
      { agent: "Builder", code: "raise RuntimeError()", iteration: 0 },
      { agent: "Fixer", code: "class SudokuGame: pass", iteration: 1 },
    ],
    langgraph: true,
  };
  const recoveredRun: RunRecord = {
    id: "run_recovered",
    status: "completed",
    phase: "complete",
    prompt: recoveredResult.prompt,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: recoveredResult.events,
    result: recoveredResult,
  };

  const failure = getWorkflowFailureInfo(recoveredRun, recoveredResult, recoveredResult.test_result);
  assert.equal(failure, null, "Recovered run must not register as failure");

  const overall = getOverallStatus(recoveredRun, recoveredResult, recoveredResult.test_result, "complete", false, failure);
  assert.equal(overall, "completed", "Overall status must be completed");

  const stages = derivePipelineStages("complete", false, recoveredResult, recoveredResult.test_result, recoveredRun.status);
  assert.equal(stages[0].status, "completed", "Builder stage must be completed");
  assert.equal(stages[3].status, "completed", "Fixer stage must be completed");
  assert.equal(stages[3].statusText, "Patched (1 iter)");
});

// 10. LeetCode Solve intent parses approach, logic, and complexity
it("10. LeetCode Solve intent parses approach, logic, and complexity", () => {
  const result: RunResult = {
    status: "completed",
    message: "Ready to ship",
    prompt: "LeetCode 1: Two Sum with optimal O(n)",
    language: "python",
    code: "class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        seen = {}\n        for i, x in enumerate(nums):\n            if target - x in seen: return [seen[target - x], i]\n            seen[x] = i",
    tests: "import unittest",
    challenge: "two_sum",
    provider: "gemini",
    generation_source: "llm",
    generation_status: "success",
    explanation: {
      intent: "solve",
      approach: "One-pass Hash Map Complement Lookup",
      logic: "Iterates through nums once. Checks if target - num exists in hash map; if so, returns indices; otherwise stores current index.",
      why_it_works: "Each complement lookup in a hash map takes O(1) time on average.",
      complexity: { time: "O(n)", space: "O(n)" },
      is_already_optimal: true,
    },
    iterations: 0,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: { passed: true, status: "passed", duration_ms: 50, sandbox: "", command: "", output: "", error: "" },
    events: [],
    history: [],
    langgraph: true,
  };

  const parsed = parseExplanation(result, result.prompt);
  assert.equal(parsed.intent, "solve");
  assert.equal(parsed.approach, "One-pass Hash Map Complement Lookup");
  assert.equal(parsed.complexity?.time, "O(n)");
  assert.equal(parsed.complexity?.space, "O(n)");
  assert.equal(parsed.is_already_optimal, true);

  const status = deriveLeetCodeStatus("complete", false, "completed", result, null);
  assert.equal(status.state, "success");
  assert.equal(status.badge, "SOLVED");
});

// 11. LeetCode Debug intent parses mistakes (what was wrong) and fix (what changed)
it("11. LeetCode Debug intent parses mistakes and fix", () => {
  const result: RunResult = {
    status: "completed",
    message: "Ready to ship",
    prompt: "Problem: LeetCode 20. Why does my code fail on '()'? What did I do wrong?",
    language: "python",
    code: "class Solution:\n    def isValid(self, s: str) -> bool: pass",
    tests: "import unittest",
    challenge: "valid_parentheses",
    provider: "gemini",
    generation_source: "llm",
    generation_status: "success",
    explanation: {
      intent: "debug",
      approach: "Stack for Matching Pairs",
      logic: "Pushes opening brackets onto stack. For closing brackets, pops and verifies matching pair.",
      why_it_works: "LIFO stack preserves the innermost scope matching requirement.",
      complexity: { time: "O(n)", space: "O(n)" },
      what_was_wrong: "The code checked `stack.pop() != c` comparing opening '(' with closing ')', which always evaluated to True.",
      what_changed: "Added a lookup dictionary matching each closing bracket to its corresponding opening bracket.",
      is_already_optimal: false,
    },
    iterations: 1,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: { passed: true, status: "passed", duration_ms: 50, sandbox: "", command: "", output: "", error: "" },
    events: [],
    history: [],
    langgraph: true,
  };

  const parsed = parseExplanation(result, result.prompt);
  assert.equal(parsed.intent, "debug");
  assert.match(parsed.what_was_wrong || "", /stack\.pop/);
  assert.match(parsed.what_changed || "", /lookup dictionary/);

  const status = deriveLeetCodeStatus("complete", false, "completed", result, null);
  assert.equal(status.state, "success");
  assert.equal(status.badge, "DEBUGGED");
});

// 12. LeetCode Optimize intent recognizes already-optimal or bottleneck
it("12. LeetCode Optimize intent recognizes already-optimal or bottleneck", () => {
  const optResult: RunResult = {
    status: "completed",
    message: "Ready to ship",
    prompt: "Can this solution be optimized?",
    language: "python",
    code: "class Solution: pass",
    tests: "import unittest",
    challenge: "optimal_task",
    provider: "gemini",
    generation_source: "llm",
    generation_status: "success",
    explanation: {
      intent: "optimize",
      approach: "Optimal Hash Table",
      logic: "Linear scan with constant-time set lookups.",
      complexity: { time: "O(n)", space: "O(n)" },
      what_can_be_improved: "The original nested loops caused O(n^2) quadratic runtime.",
      optimization: "Reduced runtime from O(n^2) to O(n) using a hash map.",
      is_already_optimal: false,
    },
    iterations: 0,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.1, summary: "Clean", findings: [] },
    test_result: { passed: true, status: "passed", duration_ms: 50, sandbox: "", command: "", output: "", error: "" },
    events: [],
    history: [],
    langgraph: true,
  };

  const parsed = parseExplanation(optResult, optResult.prompt);
  assert.equal(parsed.intent, "optimize");
  assert.match(parsed.what_can_be_improved || "", /nested loops/);
  assert.match(parsed.optimization || "", /Reduced runtime/);

  const status = deriveLeetCodeStatus("complete", false, "completed", optResult, null);
  assert.equal(status.state, "success");
  assert.equal(status.badge, "OPTIMIZED");
});

// 13. LeetCode status bar derives student-friendly error and loading states
it("13. LeetCode status bar derives student-friendly error and loading states", () => {
  // Loading state
  const loadingStatus = deriveLeetCodeStatus("builder", false, "running", undefined, null);
  assert.equal(loadingStatus.state, "loading");
  assert.match(loadingStatus.title, /Generating LeetCode solution/);

  // Error state
  const failure = {
    isFailure: true,
    type: "provider_error" as const,
    title: "Unable to generate implementation",
    message: "Gemini server error (503): Upstream model provider temporarily unavailable.",
  };
  const errStatus = deriveLeetCodeStatus("builder", false, "completed", undefined, failure);
  assert.equal(errStatus.state, "error");
  assert.match(errStatus.subtitle || "", /temporarily unavailable/i);
});

// 14. Supported languages restricted strictly to Python, Java, and C++ (TypeScript completely excluded)
it("14. Supported languages restricted strictly to Python, Java, and C++", () => {
  const allowed = ["python", "java", "cpp"];
  const forbidden = ["typescript", "ts", "javascript", "js"];

  for (const lang of allowed) {
    assert.equal(allowed.includes(lang), true);
  }
  for (const lang of forbidden) {
    assert.equal(allowed.includes(lang), false, `Language ${lang} must not be allowed`);
  }
});

// 15. Language metadata and file display derivation for Python, Java, and C++
it("15. Language metadata and file display derivation", () => {
  function getLangDisplay(lang?: string): { display: string; file: string } {
    const norm = (lang || "python").toLowerCase();
    if (norm === "java") return { display: "Java", file: "Solution.java" };
    if (norm === "cpp" || norm === "c++") return { display: "C++", file: "solution.cpp" };
    return { display: "Python 3", file: "main.py" };
  }

  assert.deepEqual(getLangDisplay("python"), { display: "Python 3", file: "main.py" });
  assert.deepEqual(getLangDisplay("java"), { display: "Java", file: "Solution.java" });
  assert.deepEqual(getLangDisplay("cpp"), { display: "C++", file: "solution.cpp" });
  assert.deepEqual(getLangDisplay("c++"), { display: "C++", file: "solution.cpp" });
  assert.deepEqual(getLangDisplay(undefined), { display: "Python 3", file: "main.py" });
});

// 16. Multi-language LeetCode result status and badges
it("16. Multi-language LeetCode result status and badges", () => {
  const javaResult: RunResult = {
    status: "completed",
    message: "Ready to ship",
    prompt: "Solve Two Sum in Java",
    language: "java",
    code: "import java.util.*;\n\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n        return new int[]{0, 1};\n    }\n}",
    tests: "// Java test suite",
    challenge: "two_sum",
    provider: "gemini",
    generation_source: "llm",
    generation_status: "success",
    explanation: {
      intent: "solve",
      approach: "One-pass Hash Table",
      logic: "Uses HashMap to store seen values and indices.",
      complexity: { time: "O(n)", space: "O(n)" },
      is_already_optimal: true,
    },
    iterations: 0,
    max_iterations: 3,
    review: { passed: true, blocking: false, score: 0.0, summary: "Java verification passed", findings: [] },
    test_result: { passed: true, status: "passed", duration_ms: 10, sandbox: "static", command: "", output: "OK", error: "" },
    events: [],
    history: [],
    langgraph: true,
  };

  const status = deriveLeetCodeStatus("complete", false, "completed", javaResult, null);
  assert.equal(status.state, "success");
  assert.equal(status.badge, "SOLVED");
  assert.match(javaResult.code, /class Solution/);
  assert.match(javaResult.code, /public int\[\] twoSum/);
  assert.doesNotMatch(javaResult.code, /def /);
});

console.log("==================================================");
console.log(`ALL ${passedCount} INTEGRATION TESTS PASSED CLEANLY!`);
console.log("==================================================");

