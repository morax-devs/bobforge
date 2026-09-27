import React from "react";
import {
  Lightbulb,
  Cpu,
  Compass,
  Clock,
  HardDrive,
  AlertCircle,
  CheckCircle2,
  TrendingUp,
  Sparkles,
  Info,
} from "lucide-react";
import type { ExplanationInfo } from "../types";

interface ExplanationPanelProps {
  explanation?: ExplanationInfo;
  isStarting?: boolean;
  isRunning?: boolean;
}

export const ExplanationPanel: React.FC<ExplanationPanelProps> = ({
  explanation,
  isStarting,
  isRunning,
}) => {
  if (isStarting || isRunning) {
    return (
      <div className="explanation-panel-container panel-loading-state">
        <div className="explanation-loading-skeleton">
          <div className="skeleton-pill" />
          <div className="skeleton-title" />
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
          <div className="skeleton-box" />
          <div className="skeleton-line" />
        </div>
      </div>
    );
  }

  if (!explanation) {
    return (
      <div className="explanation-panel-container panel-empty-state">
        <div className="explanation-empty-prompt">
          <Lightbulb size={24} className="empty-bulb-icon" />
          <h4>Algorithm & Logic Explanation</h4>
          <p>
            When you solve, debug, or optimize a LeetCode problem, detailed step-by-step
            logic, algorithmic reasoning, and complexity analysis will appear here.
          </p>
        </div>
      </div>
    );
  }

  const {
    intent = "solve",
    approach,
    logic,
    why_it_works,
    complexity,
    what_was_wrong,
    what_changed,
    what_can_be_improved,
    optimization,
    is_already_optimal,
    notes,
  } = explanation;

  const renderLogicLines = (logicContent?: string | string[]) => {
    if (!logicContent) return null;
    if (Array.isArray(logicContent)) {
      return (
        <ol className="explanation-steps-list">
          {logicContent.map((step, idx) => (
            <li key={idx} className="explanation-step-item">
              {step}
            </li>
          ))}
        </ol>
      );
    }
    // Check if logic contains numbered points (e.g. "1.", "2.", or line breaks)
    const lines = logicContent.split("\n").filter((l) => l.trim().length > 0);
    if (lines.length > 1) {
      return (
        <div className="explanation-steps-flow">
          {lines.map((line, idx) => (
            <p key={idx} className="explanation-step-paragraph">
              {line}
            </p>
          ))}
        </div>
      );
    }
    return <p className="explanation-prose">{logicContent}</p>;
  };

  return (
    <div className="explanation-panel-container">
      {/* Panel Top Header Strip */}
      <div className="explanation-header-strip">
        <div className="explanation-title-wrap">
          <Compass size={14} className="explanation-icon-accent" />
          <span className="explanation-header-title">LOGIC & COMPLEXITY</span>
        </div>

        <div className="explanation-intent-badge-wrap">
          <span className={`intent-badge badge-${intent}`}>
            {intent.toUpperCase()}
          </span>
          {is_already_optimal && (
            <span className="optimal-pill">
              <CheckCircle2 size={11} />
              <span>Already Optimal</span>
            </span>
          )}
        </div>
      </div>

      <div className="explanation-content-scroll">
        {/* DEBUGGING SECTIONS (What was wrong & What changed) */}
        {what_was_wrong && (
          <div className="explanation-card card-debug-mistake">
            <div className="card-header">
              <AlertCircle size={13} className="text-danger" />
              <span className="card-title text-danger">What was wrong</span>
            </div>
            <div className="card-body">
              <p className="debug-prose">{what_was_wrong}</p>
            </div>
          </div>
        )}

        {what_changed && (
          <div className="explanation-card card-debug-fix">
            <div className="card-header">
              <CheckCircle2 size={13} className="text-success" />
              <span className="card-title text-success">What changed</span>
            </div>
            <div className="card-body">
              <p className="debug-prose">{what_changed}</p>
            </div>
          </div>
        )}

        {/* OPTIMIZATION SECTIONS (What can be improved & Optimization) */}
        {what_can_be_improved && (
          <div className="explanation-card card-optimize-bottleneck">
            <div className="card-header">
              <TrendingUp size={13} className="text-warn" />
              <span className="card-title text-warn">Bottleneck in original code</span>
            </div>
            <div className="card-body">
              <p className="optimize-prose">{what_can_be_improved}</p>
            </div>
          </div>
        )}

        {optimization && (
          <div className="explanation-card card-optimize-result">
            <div className="card-header">
              <Sparkles size={13} className="text-accent" />
              <span className="card-title text-accent">Optimization</span>
            </div>
            <div className="card-body">
              <p className="optimize-prose">{optimization}</p>
            </div>
          </div>
        )}

        {/* APPROACH */}
        {approach && (
          <div className="explanation-card">
            <div className="card-header">
              <Lightbulb size={13} className="text-accent" />
              <span className="card-title">Approach</span>
            </div>
            <div className="card-body">
              <p className="approach-text">{approach}</p>
            </div>
          </div>
        )}

        {/* LOGIC / HOW IT WORKS */}
        {logic && (
          <div className="explanation-card">
            <div className="card-header">
              <Cpu size={13} className="text-secondary" />
              <span className="card-title">How it works</span>
            </div>
            <div className="card-body">{renderLogicLines(logic)}</div>
          </div>
        )}

        {/* WHY THIS WORKS */}
        {why_it_works && (
          <div className="explanation-card">
            <div className="card-header">
              <CheckCircle2 size={13} className="text-muted" />
              <span className="card-title">Why this works</span>
            </div>
            <div className="card-body">
              <p className="invariant-text">{why_it_works}</p>
            </div>
          </div>
        )}

        {/* COMPLEXITY METRICS */}
        <div className="explanation-card card-complexity">
          <div className="card-header">
            <Clock size={13} className="text-secondary" />
            <span className="card-title">Complexity Analysis</span>
          </div>
          <div className="card-body complexity-grid">
            <div className="complexity-cell">
              <div className="complexity-label">
                <Clock size={11} />
                <span>Time Complexity</span>
              </div>
              <div className="complexity-value">{complexity?.time || "O(n)"}</div>
            </div>

            <div className="complexity-cell">
              <div className="complexity-label">
                <HardDrive size={11} />
                <span>Space Complexity</span>
              </div>
              <div className="complexity-value">{complexity?.space || "O(1)"}</div>
            </div>
          </div>
        </div>

        {/* EXTRA NOTES IF ANY */}
        {notes && (
          <div className="explanation-notes-row">
            <Info size={12} className="text-muted" />
            <span className="notes-text">{notes}</span>
          </div>
        )}
      </div>
    </div>
  );
};
