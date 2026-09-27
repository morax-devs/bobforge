import React, { useState } from "react";
import { ShieldCheck, Terminal, Gauge, Clock, CheckCircle2, ChevronDown, ChevronUp, Wrench, AlertTriangle } from "lucide-react";
import type { Finding, Review, TestResult, EventItem } from "../types";

interface BottomPanelProps {
  review?: Review;
  testResult?: TestResult;
  events: EventItem[];
  hasResult: boolean;
}

export const BottomPanel: React.FC<BottomPanelProps> = ({
  review,
  testResult,
  events,
  hasResult,
}) => {
  const [activeTab, setActiveTab] = useState<"findings" | "console" | "risk" | "telemetry">("findings");
  const [isCollapsed, setIsCollapsed] = useState(false);

  const findings = review?.findings || [];
  const risk = review?.risk;
  const riskScore = Math.round((risk?.score ?? review?.score ?? 0) * 100);

  const formatTimestamp = (iso?: string) => {
    if (!iso) return "—";
    return new Intl.DateTimeFormat("en", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    }).format(new Date(iso));
  };

  const handleTabClick = (tab: "findings" | "console" | "risk" | "telemetry") => {
    if (activeTab === tab && !isCollapsed) {
      // Clicking active tab toggles collapse
      setIsCollapsed(true);
    } else {
      setActiveTab(tab);
      setIsCollapsed(false);
    }
  };

  return (
    <div className={`bottom-dock-container ${isCollapsed ? "dock-collapsed" : ""}`}>
      {/* Dock Tab Strip */}
      <div className="dock-tab-strip">
        <div className="dock-tabs-list">
          <button
            className={`dock-tab-button ${activeTab === "findings" && !isCollapsed ? "active-dock-tab" : ""}`}
            onClick={() => handleTabClick("findings")}
          >
            <ShieldCheck size={13} className="dock-tab-icon" />
            <span>Review Findings</span>
            <span className={`dock-count-badge ${findings.length > 0 ? "badge-warn" : "badge-neutral"}`}>
              {findings.length}
            </span>
          </button>

          <button
            className={`dock-tab-button ${activeTab === "console" && !isCollapsed ? "active-dock-tab" : ""}`}
            onClick={() => handleTabClick("console")}
          >
            <Terminal size={13} className="dock-tab-icon" />
            <span>Sandbox Console</span>
            {testResult && (
              <span className={`dock-status-pill ${testResult.passed ? "pill-pass" : "pill-fail"}`}>
                {testResult.passed ? "PASS" : "FAIL"}
              </span>
            )}
          </button>

          <button
            className={`dock-tab-button ${activeTab === "risk" && !isCollapsed ? "active-dock-tab" : ""}`}
            onClick={() => handleTabClick("risk")}
          >
            <Gauge size={13} className="dock-tab-icon" />
            <span>BobRiskNet Analysis</span>
            {hasResult && (
              <span className={`dock-count-badge ${riskScore > 50 ? "badge-warn" : "badge-neutral"}`}>
                {riskScore}%
              </span>
            )}
          </button>

          <button
            className={`dock-tab-button ${activeTab === "telemetry" && !isCollapsed ? "active-dock-tab" : ""}`}
            onClick={() => handleTabClick("telemetry")}
          >
            <Clock size={13} className="dock-tab-icon" />
            <span>Telemetry Log</span>
            <span className="dock-count-badge badge-neutral">{events.length}</span>
          </button>
        </div>

        <div className="dock-actions-right">
          <button
            className="dock-toggle-btn"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title={isCollapsed ? "Expand panel" : "Collapse panel"}
          >
            {isCollapsed ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {/* Dock Content Body (collapsible) */}
      {!isCollapsed && (
        <div className="dock-panel-body">
          {/* TAB 1: REVIEW FINDINGS */}
          {activeTab === "findings" && (
            <div className="dock-view-container">
              {(review?.semantic_review_status || review?.semantic_review) && (
                <div className="semantic-review-card">
                  <div className="semantic-card-header">
                    <span className="semantic-card-title">SEMANTIC SPECIFICATION VERIFICATION</span>
                    <span
                      className={`semantic-status-badge status-${
                        review.semantic_review_status || "unavailable"
                      }`}
                    >
                      {review.semantic_review_status === "passed"
                        ? "Specification Satisfied"
                        : review.semantic_review_status === "failed"
                        ? "Semantic Mismatch"
                        : "Offline / Unavailable"}
                    </span>
                  </div>
                  <div className="semantic-card-summary">
                    {review.semantic_review?.summary ||
                      review.summary ||
                      "Automated semantic analysis of implementation against requirements."}
                  </div>
                </div>
              )}

              {findings.length === 0 ? (
                <div className="dock-empty-state">
                  <CheckCircle2 size={15} className="dock-empty-icon-success" />
                  <div className="dock-empty-text">
                    <strong>No review findings</strong>
                    <span>
                      {hasResult
                        ? "Implementation passed AST deterministic inspections, semantic validation, and defect thresholds."
                        : "Run the pipeline to generate automated review results."}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="findings-table-view">
                  {findings.map((finding, idx) => (
                    <div key={idx} className="finding-entry-row">
                      <div className="finding-severity-cell">
                        <span className={`severity-indicator severity-${finding.severity}`}>
                          {finding.severity}
                        </span>
                        {finding.category && (
                          <span
                            className="finding-category-tag"
                            title={`Category: ${finding.category}`}
                          >
                            {finding.category.replace(/_/g, " ")}
                          </span>
                        )}
                      </div>

                      <div className="finding-meta-cell">
                        <span className="finding-loc">Line {finding.line}</span>
                      </div>

                      <div className="finding-details-cell">
                        <div className="finding-headline">{finding.title}</div>
                        <div className="finding-explanation">
                          {finding.message || finding.detail}
                        </div>
                        {finding.evidence && (
                          <div className="finding-evidence-box">
                            <span className="evidence-label">Evidence:</span>
                            <code className="evidence-code">{finding.evidence}</code>
                          </div>
                        )}
                        {finding.fix && (
                          <div className="finding-remedy-box">
                            <Wrench size={11} className="remedy-icon" />
                            <span className="remedy-prefix">Suggested Fix:</span>
                            <span className="remedy-text">{finding.fix}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: SANDBOX CONSOLE */}
          {activeTab === "console" && (
            <div className="console-view-container">
              <div className="console-header-bar">
                <div className="console-specs-left">
                  <span className="spec-token">
                    Runtime: <strong>{testResult?.sandbox || "Docker / Subprocess"}</strong>
                  </span>
                  <span className="spec-token-sep">·</span>
                  <span className="spec-token">
                    Duration: <strong>{testResult ? `${testResult.duration_ms} ms` : "—"}</strong>
                  </span>
                  <span className="spec-token-sep">·</span>
                  <span className="spec-token">
                    Verdict:{" "}
                    <strong className={testResult?.passed ? "text-success" : "text-danger"}>
                      {testResult ? testResult.status.toUpperCase() : "AWAITING RUN"}
                    </strong>
                  </span>
                  {testResult && testResult.total_count !== undefined && testResult.total_count > 0 && (
                    <>
                      <span className="spec-token-sep">·</span>
                      <span className="spec-token">
                        Tests:{" "}
                        <strong className={testResult.passed ? "text-success" : "text-danger"}>
                          {testResult.passed_count ?? 0}/{testResult.total_count} Passed
                        </strong>
                      </span>
                    </>
                  )}
                </div>
                <div className="console-specs-right">
                  <span className="spec-token">Command: python -m unittest</span>
                </div>
              </div>

              {testResult?.failing_tests && testResult.failing_tests.length > 0 && (
                <div className="console-failing-tests-bar">
                  <AlertTriangle size={12} className="text-danger" />
                  <span className="failing-tests-label">Failing Tests:</span>
                  <div className="failing-tests-tags">
                    {testResult.failing_tests.map((t, idx) => (
                      <span key={idx} className="failing-test-pill">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {testResult?.assertion_error && (
                <div className="console-assertion-alert">
                  <strong>Assertion Error:</strong> {testResult.assertion_error}
                </div>
              )}

              {testResult?.traceback_snippet && (
                <div className="console-traceback-box">
                  <div className="traceback-label">Runtime Traceback:</div>
                  <pre className="terminal-traceback">{testResult.traceback_snippet}</pre>
                </div>
              )}

              <pre className="terminal-stdout-viewport">
                {testResult
                  ? testResult.error || testResult.output || "Execution completed with 0 errors. All test contract assertions passed."
                  : "$ python -m unittest discover -p 'test_*.py'\nAwaiting test execution..."}
              </pre>
            </div>
          )}

          {/* TAB 3: BOBRISKNET ANALYSIS */}
          {activeTab === "risk" && (
            <div className="risk-view-container">
              <div className="risk-metric-box">
                <div className="risk-metric-header">
                  <span className="metric-box-title">NEURAL DEFECT PROBABILITY</span>
                  <span className="metric-model-name">{risk?.model || "BobRiskNet · 2-layer NumPy MLP"}</span>
                </div>

                <div className="risk-score-row">
                  <span className="risk-numerical-score">{riskScore}</span>
                  <span className="risk-scale-max">/ 100</span>
                  <span className={`risk-classification-tag risk-tag-${risk?.label || "low"}`}>
                    {(risk?.label || "LOW RISK").toUpperCase()}
                  </span>
                </div>

                <div className="risk-bar-track">
                  <div
                    className={`risk-bar-fill risk-fill-${risk?.label || "low"}`}
                    style={{ width: `${Math.max(4, riskScore)}%` }}
                  />
                </div>
                <span className="risk-explanation-note">
                  Scores static pattern embeddings against synthetic defect priors.
                </span>
              </div>

              <div className="risk-features-table-box">
                <div className="features-table-title">STATIC PATTERN SIGNALS</div>
                <div className="features-list-scroll">
                  {risk?.features && risk.features.length > 0 ? (
                    risk.features.map((feature, i) => (
                      <div key={i} className="feature-row-item">
                        <span className="feature-name-token">{feature.name}</span>
                        <span className="feature-weight-value">{feature.value.toFixed(2)}</span>
                      </div>
                    ))
                  ) : (
                    <div className="features-empty-note">
                      No anomalous synthetic defect signals triggered.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: TELEMETRY LOG */}
          {activeTab === "telemetry" && (
            <div className="telemetry-view-container">
              <div className="telemetry-table-header">
                <span className="col-time">TIMESTAMP</span>
                <span className="col-agent">AGENT</span>
                <span className="col-phase">PHASE</span>
                <span className="col-msg">TELEMETRY MESSAGE</span>
              </div>
              <div className="telemetry-rows-viewport">
                {events.length === 0 ? (
                  <div className="telemetry-empty-note">No event telemetry generated yet.</div>
                ) : (
                  events.map((evt) => (
                    <div key={evt.id} className="telemetry-table-row">
                      <span className="col-time">{formatTimestamp(evt.timestamp)}</span>
                      <span className="col-agent">[{evt.agent}]</span>
                      <span className="col-phase">{evt.phase}</span>
                      <span className="col-msg">{evt.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
