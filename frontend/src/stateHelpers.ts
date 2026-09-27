import { Code2, ShieldCheck, Terminal, Zap } from "lucide-react";
import type { HealthInfo, RunRecord, RunResult, TestResult, EventItem, ExplanationInfo } from "./types";
import type { StatusType } from "./components/StatusIndicator";
import type { StageInfo } from "./components/Pipeline";

export interface WorkflowFailureInfo {
  isFailure: boolean;
  isWarningOnly?: boolean;
  type:
    | "provider_error"
    | "offline_unsupported"
    | "semantic_failure"
    | "test_failure"
    | "repair_exhausted"
    | "review_blocked"
    | "provider_notice"
    | "general_error"
    | null;
  title: string;
  message: string;
}

export function getWorkflowFailureInfo(
  run: RunRecord | null,
  result?: RunResult,
  testResult?: TestResult,
  isStarting?: boolean
): WorkflowFailureInfo | null {
  if (!run || run.status === "running" || run.status === "queued" || isStarting) return null;

  if (run.status === "error") {
    return {
      isFailure: true,
      type: "general_error",
      title: "Execution Error",
      message: run.error || "An unexpected error occurred during pipeline execution.",
    };
  }

  if (result) {
    // If contract tests passed AND review is not blocking, the run shipped successfully!
    // A transient generation error subsequently repaired by Fixer is not fatal.
    const isPassing = (testResult ? testResult.passed : result.test_result?.passed) && !result.review?.blocking;

    // 1. Generation Provider Error / Unfulfilled Spec
    if (
      !isPassing &&
      (result.generation_status === "provider_error" ||
        result.challenge === "unfulfilled_specification" ||
        result.generation_source === "failed")
    ) {
      return {
        isFailure: true,
        type: "provider_error",
        title: "Unable to generate implementation",
        message:
          result.provider_warning ||
          result.message ||
          "LLM provider error occurred during code generation. Check API quota or credentials.",
      };
    }

    // 2. Offline Mode Unsupported
    if (!isPassing && result.generation_status === "offline_unsupported") {
      return {
        isFailure: true,
        type: "offline_unsupported",
        title: "Offline Generation Unsupported",
        message:
          result.provider_warning ||
          "Offline mode only supports recognized benchmark tasks. An active LLM provider (Anthropic, IBM watsonx, OpenAI, Groq) is required for arbitrary tasks.",
      };
    }

    // 3. Semantic Review Failure
    if (
      result.review?.semantic_review_status === "failed" ||
      (result.review?.blocking &&
        result.review?.findings?.some(
          (f) => f.category === "semantic_mismatch" || f.category === "placeholder_code"
        ))
    ) {
      return {
        isFailure: true,
        type: "semantic_failure",
        title: "Specification Not Satisfied",
        message:
          result.review?.semantic_review?.summary ||
          "The generated code does not satisfy the requested specification (semantic mismatch detected).",
      };
    }

    // 4. Contract Test Failure / Repair Exhaustion / Repair Blocked
    if (testResult && !testResult.passed) {
      if (result.repair_blocked || result.message?.startsWith("Repair stopped")) {
        return {
          isFailure: true,
          type: "provider_error",
          title: "Repair Halted (Provider Unavailable)",
          message:
            result.repair_failure_reason ||
            result.message ||
            "Model provider unavailable or quota exhausted during repair.",
        };
      }
      const isExhausted = (result.iterations || 0) >= (result.max_iterations || 3);
      return {
        isFailure: true,
        type: isExhausted ? "repair_exhausted" : "test_failure",
        title: isExhausted ? "Repair Budget Exhausted" : "Contract Tests Failed",
        message:
          result.message ||
          (testResult.assertion_error
            ? `Assertion failed: ${testResult.assertion_error}`
            : `${testResult.failing_tests?.length || 1} test(s) failed in sandbox execution.`),
      };
    }

    // 5. Blocking Review Findings (AST, syntax, security)
    if (result.review?.blocking) {
      return {
        isFailure: true,
        type: "review_blocked",
        title: "Code Review Blocked",
        message: result.review.summary || "Critical review findings blocked deployment.",
      };
    }

    // 6. Provider Warning (Non-fatal notice)
    if (result.provider_warning) {
      return {
        isFailure: false,
        isWarningOnly: true,
        type: "provider_notice",
        title: "Provider Notice",
        message: result.provider_warning,
      };
    }
  }

  return null;
}

export function getOverallStatus(
  run: RunRecord | null,
  result?: RunResult,
  testResult?: TestResult,
  phase?: string,
  isStarting?: boolean,
  failureInfo?: WorkflowFailureInfo | null
): StatusType {
  if (isStarting || run?.status === "running") {
    return phase === "fixer" ? "repairing" : "running";
  }
  if (run?.status === "error") return "failed";
  if (failureInfo && failureInfo.isFailure) return "failed";
  if (run?.status === "completed") {
    if (testResult && !testResult.passed) return "failed";
    if (result?.review?.blocking) return "failed";
    return "completed";
  }
  return "idle";
}

export function derivePipelineStages(
  phase: string,
  isStarting: boolean,
  result?: RunResult,
  testResult?: TestResult,
  runStatus?: string
): StageInfo[] {
  // 1. Builder Stage
  let builderStatus: StatusType = "pending";
  let builderText = "Pending";
  if (phase === "builder" || isStarting) {
    builderStatus = "running";
    builderText = "Synthesizing";
  } else if (
    result?.generation_status === "provider_error" ||
    result?.challenge === "unfulfilled_specification" ||
    result?.generation_source === "failed"
  ) {
    if (testResult?.passed && !result?.review?.blocking) {
      builderStatus = "completed";
      builderText = "Recovered";
    } else {
      builderStatus = "failed";
      builderText = "Generation Failed";
    }
  } else if (result?.generation_status === "offline_unsupported") {
    if (testResult?.passed && !result?.review?.blocking) {
      builderStatus = "completed";
      builderText = "Recovered";
    } else {
      builderStatus = "failed";
      builderText = "Offline Unsupported";
    }
  } else if (result?.generation_source === "offline_template") {
    builderStatus = "completed";
    builderText = "Offline Template";
  } else if (result?.generation_source === "llm") {
    builderStatus = "completed";
    builderText = "Synthesized";
  } else if (result?.code || runStatus === "completed") {
    builderStatus = "completed";
    builderText = "Generated";
  }

  // 2. Reviewer Stage
  let reviewerStatus: StatusType = "pending";
  let reviewerText = "Pending";
  if (phase === "reviewer") {
    reviewerStatus = "running";
    reviewerText = "Auditing AST & Spec";
  } else if (result?.review) {
    if (result.review.semantic_review_status === "failed") {
      reviewerStatus = "failed";
      reviewerText = "Semantic Mismatch";
    } else if (result.review.blocking) {
      const issueCount = result.review.findings?.length || 0;
      reviewerStatus = "failed";
      reviewerText = `${issueCount} Blocking Issue${issueCount > 1 ? "s" : ""}`;
    } else {
      const issueCount = result.review.findings?.length || 0;
      reviewerStatus = "completed";
      reviewerText = issueCount > 0 ? `${issueCount} Minor Issue${issueCount > 1 ? "s" : ""}` : "Verified";
    }
  }

  // 3. Runner Stage
  let runnerStatus: StatusType = "pending";
  let runnerText = "Pending";
  if (phase === "tester") {
    runnerStatus = "running";
    runnerText = (result?.iterations || 0) > 0 ? "Testing Patch..." : "Executing Tests";
  } else if (testResult) {
    if (testResult.passed) {
      runnerStatus = "completed";
      runnerText = `${testResult.passed_count}/${testResult.total_count} Passed`;
    } else {
      runnerStatus = "failed";
      runnerText = `${testResult.failing_tests?.length || 1} Test Failed`;
    }
  }

  // 4. Fixer Stage
  let fixerStatus: StatusType = "pending";
  let fixerText = "Pending";
  if (phase === "fixer") {
    fixerStatus = "repairing";
    const currentIter = (result?.iterations || 0) + 1;
    fixerText = `Repairing (iter ${currentIter})`;
  } else if (result) {
    if (result.iterations > 0) {
      if (testResult?.passed && !result.review?.blocking) {
        fixerStatus = "completed";
        fixerText = `Patched (${result.iterations} iter)`;
      } else if (result.repair_blocked || result.message?.startsWith("Repair stopped")) {
        fixerStatus = "failed";
        fixerText = "Repair Unavailable";
      } else {
        fixerStatus = "failed";
        fixerText = `Exhausted (${result.iterations} iter)`;
      }
    } else if (runStatus === "completed") {
      fixerStatus = "completed";
      fixerText = "Not required";
    }
  }

  return [
    {
      id: "builder",
      name: "Builder",
      icon: Code2,
      description: "Spec → Code & Tests",
      status: builderStatus,
      statusText: builderText,
    },
    {
      id: "reviewer",
      name: "Reviewer",
      icon: ShieldCheck,
      description: "AST & BobRiskNet Prior",
      status: reviewerStatus,
      statusText: reviewerText,
    },
    {
      id: "tester",
      name: "Runner",
      icon: Terminal,
      description: "Sandbox Test Execution",
      status: runnerStatus,
      statusText: runnerText,
    },
    {
      id: "fixer",
      name: "Fixer",
      icon: Zap,
      description: "Iterative Defect Repair",
      status: fixerStatus,
      statusText: fixerText,
      badge: result?.iterations ? `×${result.iterations}` : undefined,
    },
  ];
}

export function deriveCurrentMessage(
  isStarting: boolean,
  runStatus: string | undefined,
  phase: string,
  iterations: number,
  events: EventItem[],
  resultMessage?: string,
  runError?: string
): string {
  if (isStarting) return "Initiating autonomous software engineering pipeline...";
  if (runStatus === "running") {
    if (phase === "builder") return "Generating implementation and contract test suite...";
    if (phase === "reviewer") return "Auditing AST, defect risk, and semantic specification...";
    if (phase === "tester") {
      return iterations > 0
        ? `Testing repaired implementation (iteration ${iterations})...`
        : "Executing contract tests in isolated sandbox...";
    }
    if (phase === "fixer") return `Repairing — iteration ${iterations + 1}...`;
  }
  if (events.length > 0) return events[events.length - 1].message;
  if (resultMessage) return resultMessage;
  if (runError) return runError;
  return "Ready · Awaiting pipeline execution";
}

export function deriveProviderDisplay(
  result?: RunResult,
  health?: HealthInfo | null
): string | undefined {
  if (result?.provider) {
    if (result.generation_source === "offline_template") {
      return "Offline Template (Benchmark)";
    }
    if (result.generation_source === "failed") {
      return `${result.provider} (Failed)`;
    }
    let name = result.provider;
    if (result.provider === "ibm-watsonx") name = "IBM Granite";
    else if (result.provider === "anthropic") name = "Claude 3.5";
    else if (result.provider === "groq") name = "Groq LLaMA-3.3";
    else if (result.provider === "openai") name = "OpenAI";
    else if (result.provider === "offline") return "Local Sandbox";

    return result.generation_source === "llm" ? `${name} (LLM)` : name;
  }
  if (health?.provider?.model) {
    if (health.provider.provider === "ibm-watsonx") return "IBM Granite";
    if (health.provider.provider === "anthropic") {
      if (health.last_error && health.last_error.toLowerCase().includes("credit")) {
        return "Claude 3.5 (Credit Low)";
      }
      return "Claude 3.5";
    }
    if (health.provider.provider === "groq") return "Groq LLaMA-3.3";
    if (health.provider.provider === "openai") return "OpenAI";
    if (health.mode === "offline") return "Local Sandbox";
    return health.provider.model;
  }
  return undefined;
}

export interface LeetCodeStatusDisplay {
  state: "idle" | "loading" | "success" | "error";
  title: string;
  subtitle?: string;
  badge?: string;
}

export function deriveLeetCodeStatus(
  phase: string,
  isStarting: boolean,
  runStatus?: string,
  result?: RunResult,
  failureInfo?: WorkflowFailureInfo | null
): LeetCodeStatusDisplay {
  if (failureInfo && failureInfo.isFailure) {
    let cleanMessage = failureInfo.message;
    if (cleanMessage.includes("503") || cleanMessage.includes("unavailable")) {
      cleanMessage = "Upstream model provider temporarily unavailable. Please retry in a moment.";
    } else if (cleanMessage.includes("quota") || cleanMessage.includes("credit")) {
      cleanMessage = "API quota reached or credits depleted. Check provider credentials.";
    }
    return {
      state: "error",
      title: "Unable to generate solution",
      subtitle: cleanMessage,
    };
  }

  if (isStarting) {
    return {
      state: "loading",
      title: "Analyzing problem & understanding requirements...",
      subtitle: "Parsing LeetCode constraints and structure",
    };
  }

  if (runStatus === "running") {
    if (phase === "builder") {
      return {
        state: "loading",
        title: "Generating LeetCode solution...",
        subtitle: "Synthesizing class Solution with optimal time complexity",
      };
    }
    if (phase === "reviewer") {
      return {
        state: "loading",
        title: "Verifying logic, invariants & complexity...",
        subtitle: "Auditing syntax, edge cases, and constraints",
      };
    }
    if (phase === "tester") {
      return {
        state: "loading",
        title: "Validating against test cases...",
        subtitle: "Testing solution against LeetCode example test cases",
      };
    }
    if (phase === "fixer") {
      return {
        state: "loading",
        title: "Self-healing & repairing logic...",
        subtitle: "Fixing edge cases and refining implementation",
      };
    }
    return {
      state: "loading",
      title: "Processing problem...",
    };
  }

  if (runStatus === "completed" && result) {
    const intent = (result.explanation?.intent || "").toLowerCase();
    if (intent === "debug") {
      return {
        state: "success",
        title: "Bug diagnosed & fixed",
        subtitle: "Corrected LeetCode-compatible code ready to copy & submit",
        badge: "DEBUGGED",
      };
    }
    if (intent === "optimize") {
      return {
        state: "success",
        title: result.explanation?.is_already_optimal
          ? "Solution verified — already optimal"
          : "Solution optimized",
        subtitle: "Refined LeetCode solution ready to copy & submit",
        badge: "OPTIMIZED",
      };
    }
    if (intent === "explain") {
      return {
        state: "success",
        title: "Logic & complexity explained",
        subtitle: "Step-by-step walkthrough and verified LeetCode solution",
        badge: "EXPLAINED",
      };
    }
    return {
      state: "success",
      title: "Solution ready",
      subtitle: "LeetCode-compatible code ready to copy & submit",
      badge: "SOLVED",
    };
  }

  return {
    state: "idle",
    title: "Ready to solve or debug",
    subtitle: "Paste a problem, your code, or both",
  };
}

export function parseExplanation(result?: RunResult, prompt?: string): ExplanationInfo {
  const exp = result?.explanation;
  const lowPrompt = (prompt || result?.prompt || "").toLowerCase();

  let detectedIntent = exp?.intent;
  if (!detectedIntent) {
    if (lowPrompt.includes("wrong") || lowPrompt.includes("fail") || lowPrompt.includes("bug") || lowPrompt.includes("why")) {
      detectedIntent = "debug";
    } else if (lowPrompt.includes("optimize") || lowPrompt.includes("faster") || lowPrompt.includes("more efficient")) {
      detectedIntent = "optimize";
    } else if (lowPrompt.includes("explain") || lowPrompt.includes("how does") || lowPrompt.includes("walkthrough")) {
      detectedIntent = "explain";
    } else {
      detectedIntent = "solve";
    }
  }

  return {
    intent: detectedIntent,
    approach: exp?.approach || "Algorithmic Implementation",
    logic: exp?.logic || "Executes the optimal solution preserving boundary constraints and problem invariants.",
    why_it_works: exp?.why_it_works || "Directly satisfies the problem requirements with validated time and space bounds.",
    complexity: {
      time: exp?.complexity?.time || "O(n)",
      space: exp?.complexity?.space || "O(1)",
    },
    what_was_wrong: exp?.what_was_wrong || (detectedIntent === "debug" ? "The provided implementation contained boundary, indexing, or logical flaws." : null),
    what_changed: exp?.what_changed || (detectedIntent === "debug" ? "Corrected the algorithm structure to satisfy all test cases and LeetCode standards." : null),
    what_can_be_improved: exp?.what_can_be_improved || (detectedIntent === "optimize" ? "Evaluated redundant iterations and auxiliary memory usage." : null),
    optimization: exp?.optimization || (detectedIntent === "optimize" ? "Reduced asymptotic overhead to optimal complexity." : null),
    is_already_optimal: exp?.is_already_optimal ?? false,
    notes: exp?.notes || null,
  };
}
