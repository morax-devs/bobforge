import React, { useEffect, useState } from "react";

interface StartupLoaderProps {
  onComplete: () => void;
}

export const StartupLoader: React.FC<StartupLoaderProps> = ({ onComplete }) => {
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(10);
  const [isFadingOut, setIsFadingOut] = useState(false);

  const steps = [
    "Loading orchestration engine...",
    "Initializing execution sandbox...",
    "Preparing workspace...",
  ];

  useEffect(() => {
    // Stage 1: 0 - 400ms
    const t1 = setTimeout(() => {
      setProgress(45);
      setStepIndex(1);
    }, 450);

    // Stage 2: 450 - 900ms
    const t2 = setTimeout(() => {
      setProgress(85);
      setStepIndex(2);
    }, 900);

    // Stage 3: 900 - 1300ms
    const t3 = setTimeout(() => {
      setProgress(100);
    }, 1250);

    // Fade out transition: 1350ms
    const t4 = setTimeout(() => {
      setIsFadingOut(true);
    }, 1400);

    // Remove loader: 1650ms
    const t5 = setTimeout(() => {
      onComplete();
    }, 1650);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
    };
  }, [onComplete]);

  return (
    <div className={`startup-loader-overlay ${isFadingOut ? "loader-fade-out" : ""}`}>
      <div className="startup-loader-content">
        <div className="startup-logo-box">
          <svg
            width="36"
            height="36"
            viewBox="0 0 36 36"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect width="36" height="36" rx="6" fill="#0f62fe" />
            <path
              d="M10 12H26M10 18H20M10 24H24"
              stroke="#FFFFFF"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          </svg>
        </div>

        <h1 className="startup-title">BobForge</h1>
        <p className="startup-subtitle">Initializing orchestration workspace...</p>

        <div className="startup-progress-track">
          <div
            className="startup-progress-bar"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="startup-step-msg">
          <span>{steps[stepIndex]}</span>
        </div>
      </div>
    </div>
  );
};
