import React, { useState } from "react";
import { FileCode, FlaskConical, History, Copy, Check, Download, Code2 } from "lucide-react";

interface CodeWorkspaceProps {
  code: string;
  tests: string;
  language?: string;
  history?: { agent: string; code: string; iteration: number }[];
  highlightLine?: number;
  provider?: string;
  challenge?: string;
  generationSource?: string;
  generationStatus?: string;
  iterations?: number;
}

const PYTHON_KEYWORDS = new Set([
  "def", "class", "return", "if", "elif", "else", "for", "while",
  "try", "except", "finally", "raise", "import", "from", "as",
  "with", "in", "is", "not", "and", "or", "pass", "break",
  "continue", "lambda", "yield", "global", "nonlocal", "assert",
  "True", "False", "None"
]);

const JAVA_CPP_KEYWORDS = new Set([
  "class", "public", "private", "protected", "virtual", "override",
  "static", "final", "const", "void", "int", "boolean", "bool",
  "double", "float", "char", "long", "short", "auto", "return",
  "if", "else", "for", "while", "do", "switch", "case", "break",
  "continue", "try", "catch", "throw", "throws", "new", "delete",
  "this", "super", "null", "nullptr", "true", "false", "import",
  "package", "using", "namespace", "include", "typedef", "sizeof",
  "instanceof"
]);

const CODE_BUILTINS = new Set([
  "int", "str", "bool", "float", "list", "dict", "set", "tuple",
  "len", "range", "print", "isinstance", "type", "enumerate", "zip",
  "map", "filter", "all", "any", "min", "max", "sum", "sorted",
  "reversed", "open", "super", "self", "ValueError", "TypeError",
  "Exception", "KeyError", "IndexError", "AttributeError", "RuntimeError",
  "vector", "string", "unordered_map", "unordered_set", "queue",
  "priority_queue", "stack", "pair", "tuple", "cout", "cin", "endl",
  "std", "algorithm", "swap", "sort", "reverse", "String", "List",
  "ArrayList", "Map", "HashMap", "Set", "HashSet", "Queue", "LinkedList",
  "Stack", "Arrays", "Collections", "Math", "System", "Integer",
  "Boolean", "Double", "Character", "StringBuilder"
]);

function highlightCodeLine(line: string, lang: string) {
  if (!line || !line.trim()) return <span>{" "}</span>;

  const isCppOrJava = lang === "java" || lang === "cpp" || lang === "c++";
  const trimmed = line.trimStart();

  // Comment detection: // for Java/C++, # for Python
  if (isCppOrJava && (trimmed.startsWith("//") || trimmed.startsWith("/*") || trimmed.startsWith("*"))) {
    const indent = line.slice(0, line.indexOf(trimmed[0]));
    return (
      <>
        <span>{indent}</span>
        <span className="tok-comment">{line.slice(indent.length)}</span>
      </>
    );
  } else if (!isCppOrJava && trimmed.startsWith("#")) {
    const indent = line.slice(0, line.indexOf("#"));
    return (
      <>
        <span>{indent}</span>
        <span className="tok-comment">{line.slice(indent.length)}</span>
      </>
    );
  }

  // Preprocessor directives in C++ (e.g. #include <vector>)
  if (isCppOrJava && trimmed.startsWith("#")) {
    return <span className="tok-decorator">{line}</span>;
  }

  const regex = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\n]*|\/\/[^\n]*|\b\d+\b|[a-zA-Z_]\w*|[^\s\w"']+|\s+)/g;
  const tokens = line.match(regex) || [line];

  let prevToken = "";
  return (
    <>
      {tokens.map((token, i) => {
        let el = <span>{token}</span>;

        if (token.startsWith("#") || token.startsWith("//")) {
          el = <span className="tok-comment">{token}</span>;
        } else if (
          (token.startsWith('"') && token.endsWith('"')) ||
          (token.startsWith("'") && token.endsWith("'"))
        ) {
          el = <span className="tok-string">{token}</span>;
        } else if (/^\d+$/.test(token)) {
          el = <span className="tok-number">{token}</span>;
        } else if (isCppOrJava ? JAVA_CPP_KEYWORDS.has(token) : PYTHON_KEYWORDS.has(token)) {
          el = <span className="tok-keyword">{token}</span>;
        } else if (CODE_BUILTINS.has(token)) {
          el = <span className="tok-builtin">{token}</span>;
        } else if (prevToken === "def" || prevToken === "class") {
          el = <span className="tok-func">{token}</span>;
        } else if (token.startsWith("@")) {
          el = <span className="tok-decorator">{token}</span>;
        }

        if (token.trim()) {
          prevToken = token;
        }
        return <React.Fragment key={i}>{el}</React.Fragment>;
      })}
    </>
  );
}

export const CodeWorkspace: React.FC<CodeWorkspaceProps> = ({
  code,
  tests,
  language,
  history,
  highlightLine,
  provider,
  challenge,
  generationSource,
  generationStatus,
  iterations,
}) => {
  const [activeTab, setActiveTab] = useState<"code" | "tests" | "history">("code");
  const [copied, setCopied] = useState(false);

  const normLang = (language || "python").toLowerCase();
  const isCpp = normLang === "cpp" || normLang === "c++";
  const isJava = normLang === "java";
  const languageDisplay = isCpp ? "C++" : isJava ? "Java" : "Python 3";

  const activeContent = activeTab === "code" ? code : activeTab === "tests" ? tests : "";
  const lines = activeContent ? activeContent.split("\n") : [];

  const handleCopy = () => {
    if (!activeContent) return;
    navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!activeContent) return;
    const filename = isJava
      ? (activeTab === "code" ? "Solution.java" : "TestSolution.java")
      : isCpp
      ? (activeTab === "code" ? "solution.cpp" : "test_solution.cpp")
      : (activeTab === "code" ? "main.py" : "test_main.py");
    const blob = new Blob([activeContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="code-workspace-container">
      {/* Editor Tab Bar */}
      <div className="editor-tab-bar">
        <div className="editor-tabs-group">
          <button
            className={`editor-tab-item ${activeTab === "code" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("code")}
          >
            <FileCode size={13} className="tab-icon" />
            <span className="tab-name">Solution (LeetCode)</span>
            {code && <span className="tab-dirty-indicator" />}
          </button>

          <button
            className={`editor-tab-item ${activeTab === "tests" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("tests")}
            title="View verification unit test suite"
          >
            <FlaskConical size={13} className="tab-icon" />
            <span className="tab-name">Tests</span>
          </button>

          {history && history.length > 1 && (
            <button
              className={`editor-tab-item ${activeTab === "history" ? "tab-active" : ""}`}
              onClick={() => setActiveTab("history")}
              title="View revision history"
            >
              <History size={13} className="tab-icon" />
              <span className="tab-name">Revisions ({history.length - 1})</span>
            </button>
          )}

          <span className="source-badge badge-leetcode">
            LeetCode Format
          </span>
        </div>

        <div className="editor-actions-group">
          {activeContent && (
            <>
              <span className="editor-file-meta">
                {lines.length} lines · UTF-8 · {languageDisplay}
              </span>

              <button
                className="editor-tool-btn"
                onClick={handleCopy}
                title="Copy file contents"
              >
                {copied ? (
                  <>
                    <Check size={12} className="btn-success-icon" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>Copy</span>
                  </>
                )}
              </button>

              <button
                className="editor-tool-btn"
                onClick={handleDownload}
                title="Export file"
              >
                <Download size={12} />
                <span>Export</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Code Editor Viewport */}
      <div className="editor-viewport">
        {activeTab === "history" && history ? (
          <div className="history-patch-container">
            {history.map((item, index) => (
              <div key={index} className="history-patch-item">
                <div className="history-patch-header">
                  <span className="history-version-badge">Revision {item.iteration}</span>
                  <span className="history-agent-tag">Authored by {item.agent}</span>
                </div>
                <div className="history-code-block">
                  <pre>{item.code}</pre>
                </div>
              </div>
            ))}
          </div>
        ) : !activeContent ? (
          <div className="editor-empty-state">
            <Code2 size={18} className="empty-icon" />
            <span className="empty-primary-text">No generated artifacts yet</span>
            <span className="empty-secondary-text">
              Execute the pipeline to generate code and tests.
            </span>
          </div>
        ) : (
          <div className="code-table">
            {lines.map((line, index) => {
              const lineNum = index + 1;
              const isFlagged = activeTab === "code" && highlightLine === lineNum;

              return (
                <div
                  key={index}
                  className={`code-table-row ${isFlagged ? "row-flagged-warning" : ""}`}
                >
                  <span className="code-line-num">{lineNum}</span>
                  <span className="code-line-content">
                    {highlightCodeLine(line, normLang)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Editor Status Bar */}
      <div className="editor-bottom-bar">
        <div className="editor-statusbar-left">
          <span>{languageDisplay}</span>
          <span className="statusbar-sep">·</span>
          <span>LeetCode Submission Ready</span>
          {iterations !== undefined && iterations > 0 && history && history.length > 1 && (
            <>
              <span className="statusbar-sep">·</span>
              <span className="text-warn">Patched (Rev {history.length - 1})</span>
            </>
          )}
        </div>
        <div className="editor-statusbar-right">
          <span>Direct Copy-Paste</span>
          <span className="statusbar-sep">·</span>
          <span>UTF-8</span>
        </div>
      </div>
    </div>
  );
};
