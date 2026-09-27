import React from "react";
import { Code2, ShieldCheck, Terminal, Zap, Check, Loader2, X, ArrowRight } from "lucide-react";
import type { StatusType } from "./StatusIndicator";

export interface StageInfo {
  id: string;
  name: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  description: string;
  status: StatusType;
  statusText: string;
  badge?: string;
}

interface PipelineProps {
  stages: StageInfo[];
  currentIteration: number;
  maxIterations: number;
  currentMessage?: string;
  runStatus?: string;
}

export const Pipeline: React.FC<PipelineProps> = ({
  stages,
  currentIteration,
  maxIterations,
  currentMessage,
  runStatus,
}) => {
  return (
    <div className="pipeline-rail-container">
      {/* Integrated Agent Stepper Trail */}
      <div className="pipeline-stepper-track">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          const isLast = index === stages.length - 1;

          const renderStatusIcon = () => {
            switch (stage.status) {
              case "running":
                return <Loader2 className="step-spin-icon text-accent" size={12} />;
              case "completed":
                return <Check className="text-success" size={12} strokeWidth={2.5} />;
              case "failed":
                return <X className="text-danger" size={12} strokeWidth={2.5} />;
              case "repairing":
                return <Loader2 className="step-spin-icon text-warn" size={12} />;
              case "pending":
              default:
                return <span className="step-index-dot">0{index + 1}</span>;
            }
          };

          return (
            <React.Fragment key={stage.id}>
              <div
                className={`pipeline-step-item step-${stage.status}`}
                title={`${stage.name}: ${stage.description} (${stage.statusText || stage.status})`}
              >
                <div className="step-icon-wrapper">
                  {renderStatusIcon()}
                </div>
                <div className="step-text-wrapper">
                  <span className="step-name">{stage.name}</span>
                  <span className="step-substatus">
                    {stage.statusText || stage.status}
                  </span>
                </div>
                {stage.badge && (
                  <span className="step-badge">{stage.badge}</span>
                )}
              </div>

              {!isLast && (
                <div className={`step-divider-arrow ${stage.status === "completed" ? "divider-completed" : ""}`}>
                  <ArrowRight size={11} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Right-aligned Live Ticker & Cycle Indicator */}
      <div className="pipeline-rail-meta">
        <div className="rail-live-ticker">
          <span className="ticker-label">EVENT</span>
          <span className="ticker-message">
            {currentMessage || "Ready · Awaiting pipeline execution"}
          </span>
        </div>

        <div className="rail-cycle-indicator" title="Current repair loop iteration">
          <span className="cycle-label">CYCLE</span>
          <span className="cycle-value">
            {currentIteration}/{maxIterations}
          </span>
        </div>
      </div>
    </div>
  );
};

