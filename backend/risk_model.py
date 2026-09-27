"""A tiny, dependency-light neural bug-risk model.

The goal is not to replace a code review model. It is a transparent local
signal that gives the reviewer a learned prior even when no hosted LLM is
configured. The model is trained at import time on synthetic defect patterns,
then scores features extracted from the candidate program.
"""

from __future__ import annotations

from dataclasses import dataclass
import ast
import re
from typing import Any

import numpy as np


FEATURE_NAMES = [
    "syntax_error",
    "constant_base_case",
    "off_by_one_loop",
    "unsafe_eval",
    "bare_except",
    "empty_implementation",
    "mutable_default",
    "missing_input_guard",
    "long_function",
    "todo_marker",
    "has_tests",
]


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0)))


def extract_features(code: str) -> np.ndarray:
    """Convert source into interpretable static signals in [0, 1]."""

    text = code or ""
    lowered = text.lower()
    syntax_error = 0.0
    tree: ast.AST | None = None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        syntax_error = 1.0

    function_lengths: list[int] = []
    mutable_default = 0.0
    bare_except = 0.0
    constant_base_case = 0.0
    empty_implementation = 0.0
    missing_input_guard = 0.0

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno)
                function_lengths.append(max(1, end_line - node.lineno + 1))
                for default in [*node.args.defaults, *node.args.kw_defaults]:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        mutable_default = 1.0
                body = node.body
                if len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Expr)):
                    empty_implementation = 1.0
                if any(isinstance(child, ast.ExceptHandler) and child.type is None for child in ast.walk(node)):
                    bare_except = 1.0
                # A common algorithmic smell: a conditional base case returning
                # the same constant for both zero and one.
                if any(isinstance(child, ast.Return) and isinstance(child.value, ast.Constant) for child in ast.walk(node)):
                    if re.search(r"(fibonacci|fib|factorial|sequence)", node.name, re.I):
                        constant_base_case = 1.0
                if node.args.args and not any(isinstance(child, ast.If) for child in ast.walk(node)):
                    missing_input_guard = 1.0

    off_by_one_loop = float(bool(re.search(r"range\s*\(\s*\w+\s*\+\s*1\s*\)", text)))
    unsafe_eval = float(bool(re.search(r"\b(eval|exec)\s*\(", text)))
    todo_marker = float("todo" in lowered or "fixme" in lowered or "pass #" in lowered)
    has_tests = float(bool(re.search(r"\b(assert|unittest|pytest)\b", text)))
    long_function = float(any(length > 45 for length in function_lengths))

    return np.array(
        [
            syntax_error,
            constant_base_case,
            off_by_one_loop,
            unsafe_eval,
            bare_except,
            empty_implementation,
            mutable_default,
            missing_input_guard,
            long_function,
            todo_marker,
            has_tests,
        ],
        dtype=np.float64,
    )


@dataclass
class NeuralBugRiskModel:
    """A small two-layer MLP trained once on synthetic code smells."""

    seed: int = 7
    hidden_size: int = 10

    def __post_init__(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        self._fit()

    def _fit(self) -> None:
        # Each row is a synthetic feature vector; labels represent whether a
        # reviewer should investigate the candidate before shipping it.
        x = self._rng.random((240, len(FEATURE_NAMES))) * 0.16
        y = np.zeros(240, dtype=np.float64)
        for row in range(240):
            if row < 80:
                x[row, 1] = self._rng.uniform(0.7, 1.0)
                x[row, 2] = self._rng.uniform(0.4, 1.0)
                y[row] = 1.0
            elif row < 160:
                x[row, self._rng.integers(0, 7)] = self._rng.uniform(0.75, 1.0)
                y[row] = float(self._rng.random() > 0.2)
            else:
                x[row, 10] = self._rng.uniform(0.65, 1.0)
                y[row] = 0.0

        self.mean_ = x.mean(axis=0)
        self.scale_ = x.std(axis=0) + 1e-5
        x = (x - self.mean_) / self.scale_
        self.w1_ = self._rng.normal(0.0, 0.25, (x.shape[1], self.hidden_size))
        self.b1_ = np.zeros(self.hidden_size)
        self.w2_ = self._rng.normal(0.0, 0.25, self.hidden_size)
        self.b2_ = np.array(0.0)

        for _ in range(260):
            hidden = np.tanh(x @ self.w1_ + self.b1_)
            logits = hidden @ self.w2_ + self.b2_
            probs = _sigmoid(logits)
            error = probs - y
            grad_w2 = hidden.T @ error / len(x)
            grad_b2 = error.mean()
            hidden_error = np.outer(error, self.w2_) * (1.0 - hidden**2)
            grad_w1 = x.T @ hidden_error / len(x)
            grad_b1 = hidden_error.mean(axis=0)
            rate = 0.12
            self.w2_ -= rate * grad_w2
            self.b2_ -= rate * grad_b2
            self.w1_ -= rate * grad_w1
            self.b1_ -= rate * grad_b1

    def predict(self, code: str) -> dict[str, Any]:
        raw_features = extract_features(code)
        normalized = (raw_features - self.mean_) / self.scale_
        hidden = np.tanh(normalized @ self.w1_ + self.b1_)
        risk = float(_sigmoid(np.array(hidden @ self.w2_ + self.b2_)))
        evidence = [
            {"name": name, "value": round(float(value), 3)}
            for name, value in zip(FEATURE_NAMES, raw_features)
            if value > 0.5
        ]
        return {
            "score": round(risk, 3),
            "label": "high" if risk >= 0.68 else "medium" if risk >= 0.36 else "low",
            "model": "BobRiskNet · 2-layer NumPy MLP",
            "features": evidence,
        }


RISK_MODEL = NeuralBugRiskModel()

