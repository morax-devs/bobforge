import React from "react";
import { Check, Loader2, X, AlertTriangle, Clock, RefreshCw } from "lucide-react";

export type StatusType = "pending" | "running" | "completed" | "failed" | "repairing" | "idle";

interface StatusIndicatorProps {
  status: StatusType;
  label?: string;
  size?: "sm" | "md";
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  size = "md",
}) => {
  const getIcon = () => {
    switch (status) {
      case "running":
        return <Loader2 className="status-icon-spin" size={size === "sm" ? 11 : 13} />;
      case "completed":
        return <Check size={size === "sm" ? 11 : 13} />;
      case "failed":
        return <X size={size === "sm" ? 11 : 13} />;
      case "repairing":
        return <RefreshCw className="status-icon-spin" size={size === "sm" ? 11 : 13} />;
      case "pending":
      case "idle":
      default:
        return <Clock size={size === "sm" ? 11 : 13} />;
    }
  };

  const getLabel = () => {
    if (label) return label;
    switch (status) {
      case "running":
        return "Running";
      case "completed":
        return "Completed";
      case "failed":
        return "Failed";
      case "repairing":
        return "Repairing";
      case "pending":
        return "Pending";
      case "idle":
      default:
        return "Idle";
    }
  };

  return (
    <span className={`status-pill status-${status} size-${size}`}>
      {getIcon()}
      <span className="status-text">{getLabel()}</span>
    </span>
  );
};
