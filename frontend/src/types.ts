export type Finding = {
  category?: string;
  severity: "critical" | "high" | "medium" | "low";
  line: number;
  title: string;
  message?: string;
  detail: string;
  evidence?: string;
  fix: string;
};

export type SemanticReview = {
  status: "passed" | "failed" | "unavailable";
  passed: boolean;
  summary: string;
  findings?: Finding[];
};

export type Review = {
  passed?: boolean;
  findings: Finding[];
  blocking: boolean;
  score: number;
  summary: string;
  reviewer_source?: string;
  semantic_review_status?: "passed" | "failed" | "unavailable";
  semantic_review?: SemanticReview;
  risk?: { score: number; label: string; model: string; features: { name: string; value: number }[] };
};

export type TestResult = {
  passed: boolean;
  status: string;
  output: string;
  error: string;
  duration_ms: number;
  sandbox: string;
  command: string;
  failing_tests?: string[];
  assertion_error?: string;
  traceback_snippet?: string;
  passed_count?: number;
  total_count?: number;
  failure_details?: { kind: string; test: string; suite: string; error: string; traceback: string }[];
};

export type HealthInfo = {
  ok: boolean;
  service: string;
  provider: {
    provider: string;
    model: string;
    available?: boolean;
    project_id?: string;
    last_error?: string;
    last_error_category?: string;
  };
  configured_providers: string[];
  mode: string;
  last_error?: string;
};

export type EventItem = {
  id?: string;
  agent: string;
  phase: string;
  status?: string;
  message: string;
  timestamp: string;
  iteration?: number;
};

export interface ComplexityInfo {
  time?: string;
  space?: string;
}

export interface ExplanationInfo {
  intent?: "solve" | "debug" | "optimize" | "explain" | string;
  approach?: string;
  logic?: string | string[];
  why_it_works?: string;
  complexity?: ComplexityInfo;
  what_was_wrong?: string | null;
  what_changed?: string | null;
  what_can_be_improved?: string | null;
  optimization?: string | null;
  is_already_optimal?: boolean | null;
  notes?: string | null;
}

export type RunResult = {
  status: string;
  message: string;
  prompt: string;
  language: string;
  code: string;
  tests: string;
  challenge: string;
  provider: string;
  provider_warning?: string | null;
  generation_source?: "llm" | "offline_template" | "failed" | string;
  generation_status?: "success" | "provider_error" | "offline_unsupported" | "offline_template" | string;
  explanation?: ExplanationInfo;
  iterations: number;
  max_iterations: number;
  review: Review;
  test_result: TestResult;
  events: EventItem[];
  history: { agent: string; code: string; iteration: number }[];
  langgraph: boolean;
  repair_blocked?: boolean;
  repair_failure_reason?: string | null;
};

export type RunRecord = {
  id: string;
  status: "queued" | "running" | "completed" | "error";
  phase: string;
  prompt: string;
  created_at: string;
  updated_at: string;
  events: EventItem[];
  result?: RunResult;
  error?: string;
};

export type Template = { id: string; label: string; prompt: string; accent: string };

