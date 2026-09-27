import React from "react";
import { RotateCcw, Cpu } from "lucide-react";
import { StatusIndicator, StatusType } from "./StatusIndicator";

interface HeaderProps {
  status: StatusType;
  runId?: string;
  providerInfo?: string;
  onReset: () => void;
  hasActiveRun: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  runId,
  providerInfo,
  onReset,
  hasActiveRun,
}) => {
  return (
    <header className="app-header">
      <div className="header-left">
        <div className="header-logo">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect width="24" height="24" rx="4" fill="#0f62fe" />
            <path
              d="M7 8H17M7 12H13M7 16H16"
              stroke="#FFFFFF"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <span className="logo-text">BobForge</span>
          <span className="assistant-tag">LeetCode Assistant</span>
        </div>

        {providerInfo && (
          <>
            <div className="header-divider" />
            <div className="header-provider-tag" title="Active Engine / Model Provider">
              <Cpu size={12} className="provider-icon" />
              <span className="provider-tag-label">Engine:</span>
              <span className="provider-tag-val">{providerInfo}</span>
            </div>
          </>
        )}
      </div>

      <div className="header-right">
        <div className="header-status-wrapper">
          <StatusIndicator status={status} size="sm" />
        </div>

        {hasActiveRun && (
          <button
            className="header-action-btn"
            onClick={onReset}
            title="Reset current session"
          >
            <RotateCcw size={12} />
            <span>Reset</span>
          </button>
        )}
      </div>
    </header>
  );
};
