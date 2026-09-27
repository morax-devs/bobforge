import React from "react";
import { Play, Loader2, Sparkles, AlertCircle, FileCode, CornerDownLeft } from "lucide-react";
import type { Template } from "../types";

interface PromptEditorProps {
  prompt: string;
  setPrompt: (value: string) => void;
  templates: Template[];
  language: string;
  setLanguage: (lang: string) => void;
  isRunning: boolean;
  onExecute: () => void;
  error?: string;
}

export const PromptEditor: React.FC<PromptEditorProps> = ({
  prompt,
  setPrompt,
  templates,
  language,
  setLanguage,
  isRunning,
  onExecute,
  error,
}) => {
  const lineCount = prompt.split("\n").length;

  const quickPills = [
    {
      id: "two_sum",
      label: "Two Sum",
      tag: "Solve",
      prompt:
        "LeetCode 1: Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nImplement using class Solution with optimal O(n) time complexity.",
    },
    {
      id: "valid_parentheses_debug",
      label: "Valid Parentheses",
      tag: "Debug",
      prompt:
        "Problem: LeetCode 20 Valid Parentheses. Given a string s containing just '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nMy code:\nclass Solution:\n    def isValid(self, s: str) -> bool:\n        stack = []\n        for c in s:\n            if c in '({[':\n                stack.append(c)\n            else:\n                if not stack or stack.pop() != c:\n                    return False\n        return True\n\nQuestion: Why does my code fail on '()'? What did I do wrong?",
    },
    {
      id: "lru_cache_opt",
      label: "LRU Cache",
      tag: "Optimize",
      prompt:
        "LeetCode 146: Implement a Least Recently Used (LRU) Cache with O(1) time complexity for get and put operations.",
    },
    {
      id: "binary_search_explain",
      label: "Binary Search",
      tag: "Explain",
      prompt:
        "LeetCode 704: Given an array of integers nums sorted in ascending order and an integer target, write a function to search target in nums. Explain how binary search works step by step with time and space complexity.",
    },
  ];

  return (
    <div className="prompt-editor-pane">
      {/* Pane Header */}
      <div className="prompt-pane-header">
        <div className="pane-header-left">
          <FileCode size={14} className="text-accent" />
          <span className="pane-title">PROBLEM / CODE / QUESTION</span>
        </div>

        <div className="pane-header-right">
          <div className="language-selector-wrap">
            <span className="lang-label">Lang:</span>
            <select
              className="language-dropdown"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={isRunning}
            >
              <option value="python">Python 3</option>
              <option value="java">Java</option>
              <option value="cpp">C++</option>
            </select>
          </div>

          <span className="char-counter">
            {lineCount} lines · {prompt.length} chars
          </span>
        </div>
      </div>

      {/* Quick Example Suggestions */}
      <div className="quick-suggestions-bar">
        <span className="quick-suggestions-label">Examples:</span>
        <div className="quick-pills-list">
          {quickPills.map((p) => (
            <button
              key={p.id}
              className="quick-example-pill"
              onClick={() => setPrompt(p.prompt)}
              disabled={isRunning}
              title={`Load ${p.label} (${p.tag})`}
            >
              <span className={`pill-tag tag-${p.tag.toLowerCase()}`}>{p.tag}</span>
              <span className="pill-name">{p.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main Spacious Multiline Editor */}
      <div className="prompt-textarea-wrapper">
        <textarea
          className="prompt-large-textarea"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={`Paste a LeetCode problem, paste your code, or paste both...\n\nExample 1 (Solve a problem):\n"LeetCode 1480 Running Sum of 1d Array. Give me the Python solution."\n\nExample 2 (Debug your code):\n"Problem: LeetCode 20...\nMy code: class Solution: ...\nWhy is this failing?"\n\nExample 3 (Optimize):\n"Can this O(n^2) Two Sum solution be optimized to O(n)?"`}
          disabled={isRunning}
          spellCheck={false}
        />
      </div>

      {/* Execution Footer with Primary Action Button */}
      <div className="prompt-editor-footer">
        {error && (
          <div className="prompt-error-notice">
            <AlertCircle size={13} />
            <span>{error}</span>
          </div>
        )}

        <div className="prompt-action-row">
          <div className="prompt-shortcut-hint">
            <kbd>Ctrl</kbd> + <kbd>Enter</kbd> to run
          </div>

          <button
            className="solve-primary-btn"
            onClick={onExecute}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <Loader2 size={14} className="spin-icon" />
                <span>Analyzing & Solving...</span>
              </>
            ) : (
              <>
                <Sparkles size={14} />
                <span>Solve / Debug / Optimize</span>
                <CornerDownLeft size={12} className="btn-enter-icon" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
