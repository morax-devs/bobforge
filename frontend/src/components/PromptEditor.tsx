import React, { useRef, useState } from "react";
import {
  Play,
  Loader2,
  Sparkles,
  AlertCircle,
  FileCode,
  CornerDownLeft,
  Image as ImageIcon,
  X,
  UploadCloud,
  Maximize2,
  Trash2,
} from "lucide-react";
import type { Template } from "../types";

interface PromptEditorProps {
  prompt: string;
  setPrompt: (value: string) => void;
  images?: string[];
  setImages?: React.Dispatch<React.SetStateAction<string[]>>;
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
  images = [],
  setImages,
  templates,
  language,
  setLanguage,
  isRunning,
  onExecute,
  error,
}) => {
  const lineCount = prompt.split("\n").length;
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [modalImage, setModalImage] = useState<string | null>(null);

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

  const processImageFiles = (files: FileList | File[]) => {
    if (!setImages) return;
    const fileList = Array.from(files);
    const validImageFiles = fileList.filter((f) => f.type.startsWith("image/"));
    if (validImageFiles.length === 0) return;

    validImageFiles.forEach((file) => {
      // 10MB limit per image
      if (file.size > 10 * 1024 * 1024) {
        alert(`Image "${file.name}" exceeds the 10MB limit.`);
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        const result = e.target?.result;
        if (typeof result === "string" && result) {
          setImages((prev) => [...prev, result]);
        }
      };
      reader.readAsDataURL(file);
    });
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    if (isRunning) return;
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageFiles: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) {
          imageFiles.push(file);
        }
      }
    }

    if (imageFiles.length > 0) {
      processImageFiles(imageFiles);
      // If there's no regular text being pasted, suppress standard textarea paste
      if (!e.clipboardData.getData("text")) {
        e.preventDefault();
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isRunning && !isDragging) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (isRunning) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processImageFiles(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processImageFiles(e.target.files);
      e.target.value = "";
    }
  };

  const handleRemoveImage = (indexToRemove: number) => {
    if (setImages) {
      setImages((prev) => prev.filter((_, idx) => idx !== indexToRemove));
    }
  };

  const handleClearAllImages = () => {
    if (setImages) {
      setImages([]);
    }
  };

  return (
    <div className="prompt-editor-pane">
      {/* Hidden File Picker Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={handleFileInputChange}
        style={{ display: "none" }}
        disabled={isRunning}
      />

      {/* Pane Header */}
      <div className="prompt-pane-header">
        <div className="pane-header-left">
          <FileCode size={14} className="text-accent" />
          <span className="pane-title">PROBLEM / CODE / SCREENSHOT</span>
        </div>

        <div className="pane-header-right">
          <button
            type="button"
            className="header-attach-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isRunning}
            title="Attach screenshot or diagram (or paste Ctrl+V)"
          >
            <ImageIcon size={12} />
            <span>Attach Image</span>
            {images.length > 0 && <span className="attach-count-badge">{images.length}</span>}
          </button>

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

      {/* Main Spacious Multiline Editor with Drag & Drop */}
      <div
        className={`prompt-textarea-wrapper ${isDragging ? "drag-over-active" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="drag-drop-overlay">
            <UploadCloud size={32} className="drag-drop-icon" />
            <span className="drag-drop-text">Drop screenshot or diagram image here</span>
          </div>
        )}

        <textarea
          className="prompt-large-textarea"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onPaste={handlePaste}
          placeholder={`Paste a LeetCode problem, paste your code, or paste both...\n\n💡 Tip: You can also attach screenshots of problem diagrams, binary trees, tables, or terminal error tracebacks! Just paste directly (Ctrl+V) or click "Attach Image".\n\nExample 1 (Solve):\n"LeetCode 1480 Running Sum of 1d Array. Give me the solution."\n\nExample 2 (Debug):\n"Problem: LeetCode 20...\nMy code: class Solution: ...\nWhy is this failing?"`}
          disabled={isRunning}
          spellCheck={false}
        />

        {/* Attached Images Tray */}
        {images.length > 0 && (
          <div className="attached-images-tray">
            <div className="attached-tray-header">
              <div className="attached-tray-title">
                <ImageIcon size={13} className="text-accent" />
                <span>Attached Screenshots / Diagrams ({images.length})</span>
              </div>
              <button
                type="button"
                className="clear-images-btn"
                onClick={handleClearAllImages}
                disabled={isRunning}
                title="Remove all attached images"
              >
                <Trash2 size={11} />
                <span>Clear all</span>
              </button>
            </div>

            <div className="attached-thumbnails-row">
              {images.map((img, idx) => (
                <div key={idx} className="attached-thumbnail-card">
                  <div
                    className="thumbnail-img-wrap"
                    onClick={() => setModalImage(img)}
                    title="Click to expand"
                  >
                    <img src={img} alt={`Attached preview ${idx + 1}`} />
                    <div className="thumbnail-zoom-hint">
                      <Maximize2 size={12} />
                    </div>
                  </div>
                  <div className="thumbnail-card-info">
                    <span className="thumbnail-index-tag">Img {idx + 1}</span>
                    <button
                      type="button"
                      className="thumbnail-remove-btn"
                      onClick={() => handleRemoveImage(idx)}
                      disabled={isRunning}
                      title="Remove image"
                    >
                      <X size={11} />
                    </button>
                  </div>
                </div>
              ))}

              <button
                type="button"
                className="add-more-images-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={isRunning}
                title="Add another screenshot or diagram"
              >
                <ImageIcon size={14} />
                <span>+ Add</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Image Modal Lightbox */}
      {modalImage && (
        <div className="image-preview-modal-backdrop" onClick={() => setModalImage(null)}>
          <div className="image-preview-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="image-preview-modal-header">
              <span>Attached Screenshot / Diagram</span>
              <button
                type="button"
                className="image-preview-close-btn"
                onClick={() => setModalImage(null)}
              >
                <X size={16} />
              </button>
            </div>
            <div className="image-preview-modal-body">
              <img src={modalImage} alt="Enlarged screenshot preview" />
            </div>
          </div>
        </div>
      )}

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
            <span><kbd>Ctrl</kbd> + <kbd>Enter</kbd> to run</span>
            <span className="shortcut-separator">·</span>
            <span className="screenshot-hint"><kbd>Ctrl</kbd>+<kbd>V</kbd> paste screenshot</span>
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
