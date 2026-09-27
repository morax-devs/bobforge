import React from "react";
import { CheckCircle2, AlertTriangle, Loader2, Sparkles, RotateCcw } from "lucide-react";
import type { LeetCodeStatusDisplay } from "../stateHelpers";

interface SubtleStatusBarProps {
  status: LeetCodeStatusDisplay;
  onRetry?: () => void;
}

export const SubtleStatusBar: React.FC<SubtleStatusBarProps> = ({ status, onRetry }) => {
  const { state, title, subtitle, badge } = status;

  return (
    <div className={`subtle-status-bar status-state-${state}`}>
      <div className="status-bar-left">
        <div className="status-icon-bubble">
          {state === "loading" && <Loader2 size={13} className="spin-icon text-accent" />}
          {state === "success" && <CheckCircle2 size={13} className="text-success" />}
          {state === "error" && <AlertTriangle size={13} className="text-danger" />}
          {state === "idle" && <Sparkles size={13} className="text-muted" />}
        </div>

        <div className="status-text-group">
          <span className="status-main-title">{title}</span>
          {subtitle && <span className="status-subtitle">{subtitle}</span>}
        </div>
      </div>

      <div className="status-bar-right">
        {badge && <span className="status-pill-badge">{badge}</span>}
        {state === "error" && onRetry && (
          <button className="status-retry-btn" onClick={onRetry}>
            <RotateCcw size={12} />
            <span>Retry</span>
          </button>
        )}
      </div>
    </div>
  );
};
