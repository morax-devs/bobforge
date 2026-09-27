import React from "react";
import { Code2, Bug, TrendingUp, BookOpen, ArrowRight } from "lucide-react";

interface EmptyStateProps {
  onSelectPrompt: (promptText: string) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onSelectPrompt }) => {
  const suggestions = [
    {
      icon: Code2,
      category: "Solve a problem",
      label: "Two Sum",
      tag: "SOLVE",
      prompt:
        "LeetCode 1: Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nImplement in Python using class Solution with optimal O(n) time complexity.",
      description: "Generate optimal LeetCode solution with class Solution structure.",
    },
    {
      icon: Bug,
      category: "Debug my code",
      label: "Valid Parentheses",
      tag: "DEBUG",
      prompt:
        "Problem: LeetCode 20 Valid Parentheses. Given a string s containing just '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nMy code:\nclass Solution:\n    def isValid(self, s: str) -> bool:\n        stack = []\n        for c in s:\n            if c in '({[':\n                stack.append(c)\n            else:\n                if not stack or stack.pop() != c:\n                    return False\n        return True\n\nQuestion: Why does my code fail on '()'? What did I do wrong?",
      description: "Diagnose logic or edge-case bugs and generate the fix.",
    },
    {
      icon: TrendingUp,
      category: "Optimize",
      label: "LRU Cache",
      tag: "OPTIMIZE",
      prompt:
        "LeetCode 146: Implement a Least Recently Used (LRU) Cache with O(1) time complexity for get and put operations.",
      description: "Upgrade an existing approach from O(n^2) or O(n) to optimal time/space.",
    },
    {
      icon: BookOpen,
      category: "Explain",
      label: "Binary Search",
      tag: "EXPLAIN",
      prompt:
        "LeetCode 704: Given an array of integers nums sorted in ascending order and an integer target, write a function to search target in nums. Explain how binary search works step by step with time and space complexity.",
      description: "Get a clear step-by-step walkthrough of the algorithm and complexity.",
    },
  ];

  return (
    <div className="leetcode-empty-state-view">
      <div className="empty-state-hero">
        <h3 className="empty-hero-title">Paste a LeetCode problem or your code</h3>
        <p className="empty-hero-subtitle">
          BobForge analyzes your problem, diagnoses bugs, optimizes algorithms, and produces
          clean LeetCode-ready code with complete step-by-step logic explanations.
        </p>
      </div>

      <div className="empty-suggestions-grid">
        {suggestions.map((s, idx) => {
          const Icon = s.icon;
          return (
            <button
              key={idx}
              className="empty-suggestion-card"
              onClick={() => onSelectPrompt(s.prompt)}
            >
              <div className="card-top-row">
                <div className="icon-wrapper">
                  <Icon size={16} />
                </div>
                <span className={`tag-badge tag-${s.tag.toLowerCase()}`}>{s.tag}</span>
              </div>
              <div className="card-info">
                <span className="card-category">{s.category}</span>
                <h4 className="card-problem-title">{s.label}</h4>
                <p className="card-desc">{s.description}</p>
              </div>
              <div className="card-action-cue">
                <span>Try this example</span>
                <ArrowRight size={12} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
