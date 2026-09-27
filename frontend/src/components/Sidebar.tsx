import React from "react";
import { Play, Loader2, AlertCircle, Sparkles, Activity, FileCode2 } from "lucide-react";
import type { Template, EventItem } from "../types";

interface SidebarProps {
  prompt: string;
  setPrompt: (value: string) => void;
  templates: Template[];
  iterations: number;
  setIterations: (value: number) => void;
  runTests: boolean;
  setRunTests: (value: boolean) => void;
  isRunning: boolean;
  onExecute: () => void;
  error: string;
  events?: EventItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({
  prompt,
  setPrompt,
  templates,
  iterations,
  setIterations,
  runTests,
  setRunTests,
  isRunning,
  onExecute,
  error,
  events = [],
}) => {
  const popularTemplates = templates.slice(0, 3);

  const formatEventTime = (iso?: string) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <aside className="workbench-sidebar">
      {/* 1. TASK SPECIFICATION */}
      <div className="sidebar-section">
        <div className="sidebar-section-header">
          <span className="section-title">SPECIFICATION</span>
          <span className="section-meta">{prompt.length} chars</span>
        </div>

        <div className="sidebar-textarea-wrap">
          <textarea
            className="sidebar-textarea"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Specify your Python module or class requirement in detail. Include input types, exceptions to validate, and edge cases..."
            rows={5}
            disabled={isRunning}
          />
        </div>

        {/* Starter Contract Selector */}
        <div className="starter-contracts-selector">
          <div className="contracts-selector-header">
            <span className="sub-title">STARTER CONTRACTS</span>
          </div>

          <div className="contracts-select-box">
            <select
              className="contracts-dropdown"
              onChange={(e) => {
                if (e.target.value) setPrompt(e.target.value);
              }}
              defaultValue=""
              disabled={isRunning}
            >
              <option value="" disabled>
                Select from {templates.length || 8} challenge contracts...
              </option>
              {templates.map((t) => (
                <option key={t.id} value={t.prompt}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Quick 1-click pills */}
          <div className="quick-contract-pills">
            {(popularTemplates.length > 0
              ? popularTemplates
              : [
                  { id: "fib", label: "Fibonacci (Demo)", prompt: "Build a Python function that returns the nth Fibonacci number. Handle n=0 and n=1, reject negative values, validate types, and include a CLI." },
                  { id: "lru", label: "LRU Cache", prompt: "Implement a Least Recently Used (LRU) Cache with O(1) get and put operations, fixed capacity eviction, and boundary test assertions." },
                  { id: "dijk", label: "Dijkstra", prompt: "Build Dijkstra's shortest path algorithm for weighted directed graphs using a min-heap priority queue with edge validation." },
                ]
            ).map((t) => (
              <button
                key={t.id}
                className="quick-pill-btn"
                onClick={() => setPrompt(t.prompt)}
                disabled={isRunning}
                title={t.prompt}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. EXECUTION PARAMETERS */}
      <div className="sidebar-section sidebar-section-bordered">
        <div className="sidebar-section-header">
          <span className="section-title">CONFIGURATION</span>
        </div>

        <div className="sidebar-param-grid">
          <div className="param-item-row">
            <span className="param-label">Runtime</span>
            <span className="param-badge">Python 3.12+ (Standard Lib)</span>
          </div>

          <div className="param-item-row">
            <span className="param-label">Repair Cycles</span>
            <div className="stepper-widget">
              <button
                onClick={() => setIterations(Math.max(1, iterations - 1))}
                disabled={isRunning || iterations <= 1}
                title="Decrease"
              >
                −
              </button>
              <span className="stepper-value">{iterations}</span>
              <button
                onClick={() => setIterations(Math.min(5, iterations + 1))}
                disabled={isRunning || iterations >= 5}
                title="Increase"
              >
                +
              </button>
            </div>
          </div>

          <div className="param-item-row">
            <span className="param-label">Sandbox Guard</span>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={runTests}
                onChange={(e) => setRunTests(e.target.checked)}
                disabled={isRunning}
              />
              <span className="toggle-slider" />
            </label>
          </div>
        </div>

        {/* Primary Action Button */}
        <div className="sidebar-execute-box">
          <button
            className="execute-pipeline-btn"
            onClick={onExecute}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <Loader2 className="btn-icon-spin" size={13} />
                <span>Running Pipeline...</span>
              </>
            ) : (
              <>
                <Play size={13} fill="currentColor" />
                <span>Execute Pipeline</span>
              </>
            )}
          </button>

          <div className="execute-shortcut-label">
            <span>Shortcut:</span>
            <kbd>Ctrl</kbd> + <kbd>Enter</kbd>
          </div>

          {error && (
            <div className="sidebar-error-banner">
              <AlertCircle size={13} />
              <span>{error}</span>
            </div>
          )}
        </div>
      </div>

      {/* 3. MISSION CONTROL: LIVE ACTIVITY STREAM */}
      <div className="sidebar-section sidebar-section-bordered sidebar-activity-section">
        <div className="sidebar-section-header">
          <div className="activity-header-left">
            <Activity size={12} className="activity-icon" />
            <span className="section-title">AGENT ACTIVITY</span>
          </div>
          <span className="section-meta">{events.length} events</span>
        </div>

        <div className="activity-stream-viewport">
          {events.length === 0 ? (
            <div className="activity-empty-state">
              <span>Ready. Events will stream here during pipeline execution.</span>
            </div>
          ) : (
            <div className="activity-stream-list">
              {events.slice(-6).map((evt) => (
                <div key={evt.id} className="activity-stream-item">
                  <div className="activity-item-top">
                    <span className={`activity-agent-tag agent-${evt.agent.toLowerCase()}`}>
                      {evt.agent}
                    </span>
                    <span className="activity-timestamp">
                      {formatEventTime(evt.timestamp)}
                    </span>
                  </div>
                  <div className="activity-message">{evt.message}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
