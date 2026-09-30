import React, { useEffect, useMemo, useState } from "react";
import { Header } from "./components/Header";
import { PromptEditor } from "./components/PromptEditor";
import { CodeWorkspace } from "./components/CodeWorkspace";
import { ExplanationPanel } from "./components/ExplanationPanel";
import { SubtleStatusBar } from "./components/SubtleStatusBar";
import { EmptyState } from "./components/EmptyState";
import { StartupLoader } from "./components/StartupLoader";
import { StatusType } from "./components/StatusIndicator";
import { createRun, fetchHealth, fetchRun, fetchTemplates } from "./api";
import type { HealthInfo, RunRecord, Template } from "./types";
import {
  getWorkflowFailureInfo,
  getOverallStatus,
  deriveCurrentMessage,
  deriveProviderDisplay,
  deriveLeetCodeStatus,
  parseExplanation,
} from "./stateHelpers";

const defaultPrompt =
  "LeetCode 1: Two Sum\n\nGiven an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nImplement the solution using class Solution with optimal O(n) time complexity.";

export function App() {
  const [hasBootstrapped, setHasBootstrapped] = useState(false);
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [images, setImages] = useState<string[]>([]);
  const [language, setLanguage] = useState("python");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);

  // Fetch challenge templates and engine health on initial mount
  useEffect(() => {
    fetchTemplates()
      .then(setTemplates)
      .catch(() => undefined);
    fetchHealth()
      .then(setHealth)
      .catch(() => undefined);
  }, []);

  // Poll for active run updates
  useEffect(() => {
    if (!run || run.status === "completed" || run.status === "error") return;
    const interval = window.setInterval(() => {
      fetchRun(run.id)
        .then(setRun)
        .catch((err: Error) => setError(err.message));
    }, 550);
    return () => window.clearInterval(interval);
  }, [run?.id, run?.status]);

  // Execute pipeline
  async function handleExecute() {
    const hasPrompt = prompt.trim().length >= 8;
    const hasImages = images.length > 0;
    if (!hasPrompt && !hasImages) {
      setError("Please provide a problem prompt, code snippet, or attach an image/screenshot.");
      return;
    }
    setError("");
    setRun(null);
    setIsStarting(true);
    try {
      const created = await createRun({
        prompt: prompt.trim() || "Analyze the attached image/screenshot (LeetCode problem, code, or error message) and provide the correct solution, explanation, and error diagnosis.",
        language,
        max_iterations: 3,
        run_tests: true,
        images,
      });
      const initialRecord = await fetchRun(created.id);
      setRun(initialRecord);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution request failed.");
    } finally {
      setIsStarting(false);
    }
  }

  // Reset session
  function handleReset() {
    setRun(null);
    setError("");
    setImages([]);
  }

  // Keyboard shortcut: Ctrl+Enter / Cmd+Enter
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !isStarting && run?.status !== "running") {
        e.preventDefault();
        handleExecute();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [prompt, images, isStarting, run?.status]);

  const result = run?.result;
  const phase = run?.phase || "queued";
  const events = run?.events || [];
  const testResult = result?.test_result;

  // Derive failure information
  const failureInfo = useMemo(
    () => getWorkflowFailureInfo(run, result, testResult, isStarting),
    [run, result, testResult, isStarting]
  );

  // Overall status for header
  const overallStatus: StatusType = useMemo(
    () => getOverallStatus(run, result, testResult, phase, isStarting, failureInfo),
    [run, result, testResult, phase, isStarting, failureInfo]
  );

  // Engine display
  const providerDisplay = useMemo(
    () => deriveProviderDisplay(result, health),
    [result, health]
  );

  // LeetCode subtle status display
  const leetCodeStatus = useMemo(
    () => deriveLeetCodeStatus(phase, isStarting, run?.status, result, failureInfo),
    [phase, isStarting, run?.status, result, failureInfo]
  );

  // Educational explanation breakdown
  const explanation = useMemo(
    () => (result ? parseExplanation(result, prompt) : undefined),
    [result, prompt]
  );

  const isExecuting = isStarting || run?.status === "running";
  const hasOutput = Boolean(result || isExecuting || (failureInfo && failureInfo.isFailure));

  return (
    <>
      {!hasBootstrapped && (
        <StartupLoader onComplete={() => setHasBootstrapped(true)} />
      )}

      <div className="leetcode-app-layout">
        {/* Simplified Header */}
        <Header
          status={overallStatus}
          runId={run?.id}
          providerInfo={providerDisplay}
          onReset={handleReset}
          hasActiveRun={Boolean(run)}
        />

        {/* Main Content: Left Input Pane + Right Output Workspace */}
        <div className="leetcode-workbench-body">
          {/* Left Column: Prominent Problem / Code Editor */}
          <aside className="leetcode-input-column">
            <PromptEditor
              prompt={prompt}
              setPrompt={setPrompt}
              images={images}
              setImages={setImages}
              templates={templates}
              language={language}
              setLanguage={setLanguage}
              isRunning={isExecuting}
              onExecute={handleExecute}
              error={error}
            />
          </aside>

          {/* Right Column: Code Output + Logic Explanation */}
          <main className="leetcode-output-column">
            {/* Subtle Status Line replacing old heavy pipeline */}
            <SubtleStatusBar
              status={leetCodeStatus}
              onRetry={handleExecute}
            />

            {!hasOutput ? (
              <EmptyState onSelectPrompt={(p) => setPrompt(p)} />
            ) : (
              <div className="leetcode-dual-workspace">
                {/* 1. LeetCode-Ready Code Editor */}
                <div className="dual-pane-code">
                  <CodeWorkspace
                    code={result?.code || ""}
                    tests={result?.tests || ""}
                    language={result?.language || language}
                    history={result?.history}
                    provider={result?.provider}
                    challenge={result?.challenge}
                    generationSource={result?.generation_source}
                    generationStatus={result?.generation_status}
                    iterations={result?.iterations}
                  />
                </div>

                {/* 2. Structured Logic & Complexity Explanation Panel */}
                <div className="dual-pane-explanation">
                  <ExplanationPanel
                    explanation={explanation}
                    isStarting={isStarting}
                    isRunning={run?.status === "running"}
                  />
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </>
  );
}

export default App;
