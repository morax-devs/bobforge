"""Comprehensive tests for Phase 3 Reviewer: AST, BobRiskNet, and LLM semantic verification."""

from unittest.mock import patch

from backend.agents import REVIEWER_SYSTEM_PROMPT, review_code
from backend.model_client import JsonGenerationResult, ProviderError


def test_valid_arbitrary_implementation_passes_semantic_review():
    code = '''"""Binary search tree implementation."""

class Node:
    def __init__(self, key: int):
        self.key = key
        self.left = None
        self.right = None

class BinarySearchTree:
    def __init__(self):
        self.root = None

    def insert(self, key: int) -> None:
        if not isinstance(key, int):
            raise TypeError("Key must be integer")
        self.root = self._insert(self.root, key)

    def _insert(self, node, key):
        if not node:
            return Node(key)
        if key < node.key:
            node.left = self._insert(node.left, key)
        else:
            node.right = self._insert(node.right, key)
        return node
'''
    prompt = "Build a binary search tree in Python with insert and search methods"
    mock_res = JsonGenerationResult(
        data={
            "passed": True,
            "summary": "Implementation satisfies binary search tree requirements cleanly.",
            "findings": [],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "anthropic", "active": "anthropic"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        review = review_code(code, prompt)

    assert review["passed"] is True
    assert review["blocking"] is False
    assert review["semantic_review_status"] == "passed"
    assert review["semantic_review"]["passed"] is True
    assert len(review["findings"]) == 0
    assert "ast_bobrisknet_anthropic" in review["reviewer_source"]


def test_placeholder_implementation_fails_semantic_review():
    code = '''"""Placeholder solution."""

def solve(input_data):
    """Generic solve function."""
    if input_data is None:
        raise ValueError("Input data cannot be None")
    return input_data
'''
    prompt = "Build a high-performance 2D matrix multiplication engine in Python"
    mock_res = JsonGenerationResult(
        data={
            "passed": False,
            "summary": "Generated code is a generic placeholder, not a matrix multiplication engine.",
            "findings": [
                {
                    "category": "placeholder_code",
                    "severity": "high",
                    "line": 3,
                    "title": "Generic placeholder function detected",
                    "message": "The implementation contains only a generic solve() stub rather than matrix multiplication.",
                    "evidence": "def solve(input_data): return input_data",
                    "fix": "Implement a 2D matrix multiplication function with row/col dimension validation.",
                }
            ],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "anthropic", "active": "anthropic"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        review = review_code(code, prompt)

    assert review["passed"] is False
    assert review["blocking"] is True
    assert review["semantic_review_status"] == "failed"
    assert review["semantic_review"]["passed"] is False
    assert any(f["category"] == "placeholder_code" for f in review["findings"])
    assert any(f["severity"] == "high" for f in review["findings"])


def test_sudoku_customtkinter_with_generic_code_fails_semantic_review():
    code = '''"""Placeholder code."""

def solve(input_data):
    return input_data
'''
    prompt = "Build a simple Sudoku game using Python and CustomTkinter"
    mock_res = JsonGenerationResult(
        data={
            "passed": False,
            "summary": "Missing Sudoku board logic and CustomTkinter GUI interface.",
            "findings": [
                {
                    "category": "semantic_mismatch",
                    "severity": "high",
                    "line": 3,
                    "title": "Missing Sudoku and CustomTkinter implementation",
                    "message": "The implementation does not provide the requested Sudoku game or CustomTkinter GUI.",
                    "evidence": "No CustomTkinter imports, Sudoku board representation, puzzle validation, or GUI event handling are present.",
                    "fix": "Import customtkinter, implement a 9x9 board representation with puzzle validation and interactive UI buttons.",
                }
            ],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "anthropic", "active": "anthropic"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        review = review_code(code, prompt)

    assert review["passed"] is False
    assert review["blocking"] is True
    assert review["semantic_review_status"] == "failed"
    assert any(f["category"] == "semantic_mismatch" for f in review["findings"])
    assert any("CustomTkinter" in f["evidence"] for f in review["findings"])


def test_arbitrary_algorithm_request_with_incorrect_implementation_fails_semantic_review():
    code = '''"""Dijkstra algorithm attempt."""

def dijkstra(graph, start):
    """Stub returning empty dict."""
    return {}
'''
    prompt = "Build Dijkstra's shortest path algorithm for weighted directed graphs."
    mock_res = JsonGenerationResult(
        data={
            "passed": False,
            "summary": "Function returns an empty dictionary without computing graph shortest paths.",
            "findings": [
                {
                    "category": "missing_requirement",
                    "severity": "high",
                    "line": 3,
                    "title": "Dijkstra shortest path algorithm not implemented",
                    "message": "The dijkstra function immediately returns {} without visiting graph nodes or calculating distance relaxations.",
                    "evidence": "return {}",
                    "fix": "Implement Dijkstra's algorithm using heapq priority queue and distance map.",
                }
            ],
        },
        provider="granite",
        status="success",
        source="granite",
    )

    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "granite", "active": "granite"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        review = review_code(code, prompt)

    assert review["passed"] is False
    assert review["blocking"] is True
    assert review["semantic_review_status"] == "failed"
    assert any(f["category"] == "missing_requirement" for f in review["findings"])
    assert any(f["severity"] == "high" for f in review["findings"])


def test_semantic_findings_contain_actionable_information():
    code = "def parse(x): return x"
    prompt = "Build an RFC-compliant CSV parser with escape character handling"
    mock_res = JsonGenerationResult(
        data={
            "passed": False,
            "summary": "Missing CSV parsing features.",
            "findings": [
                {
                    "category": "semantic_mismatch",
                    "severity": "high",
                    "line": 1,
                    "title": "Omitted CSV delimiter and escape handling",
                    "message": "The parse function simply returns its input without parsing comma-delimited columns.",
                    "evidence": "def parse(x): return x",
                    "fix": "Split by delimiter while respecting quotes and escaped characters.",
                }
            ],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "anthropic", "active": "anthropic"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        review = review_code(code, prompt)

    finding = review["findings"][0]
    # Verify actionable structured fields
    assert finding["category"] == "semantic_mismatch"
    assert finding["severity"] == "high"
    assert isinstance(finding["message"], str) and len(finding["message"]) > 0
    assert isinstance(finding["evidence"], str) and len(finding["evidence"]) > 0
    assert isinstance(finding["fix"], str) and len(finding["fix"]) > 0
    assert isinstance(finding["line"], int)


def test_llm_reviewer_unavailable_is_represented_explicitly():
    code = '''"""Addition utility."""

def add(a: int, b: int) -> int:
    """Return sum of two integers."""
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Arguments must be integers")
    return a + b
'''
    prompt = "Build an addition utility that validates types"

    # Offline mode: no LLM active
    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "offline", "active": "offline"}):
        review = review_code(code, prompt)

    # Must NOT silently claim semantic verification passed
    assert review["semantic_review"]["status"] == "unavailable"
    assert review["semantic_review"]["passed"] is False
    assert review["semantic_review_status"] == "unavailable"
    assert review["reviewer_source"] == "ast_bobrisknet"
    assert "Semantic review unavailable" in review["semantic_review"]["summary"]

    # Also test provider failure during review
    quota_err = ProviderError(
        provider="anthropic",
        category="quota_error",
        message="Anthropic quota error: Credit balance is too low (Error 400).",
        status_code=400,
    )
    failed_res = JsonGenerationResult(
        data=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )

    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "anthropic", "active": "anthropic"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=failed_res):
        review2 = review_code(code, prompt)

    assert review2["semantic_review"]["status"] == "unavailable"
    assert review2["semantic_review"]["passed"] is False
    assert review2["semantic_review_status"] == "unavailable"
    assert "Anthropic quota error" in review2["semantic_review"]["summary"]


def test_existing_ast_and_security_checks_continue_to_work():
    # 1. Critical syntax error
    bad_syntax = "def broken(:\n    pass\n"
    review_syntax = review_code(bad_syntax, "test syntax")
    assert review_syntax["passed"] is False
    assert review_syntax["blocking"] is True
    assert any(f["severity"] == "critical" and f["category"] == "syntax_error" for f in review_syntax["findings"])

    # 2. Dynamic execution (eval/exec) security vulnerability
    eval_code = "def calc(expr):\n    return eval(expr)\n"
    review_eval = review_code(eval_code, "test eval")
    assert review_eval["passed"] is False
    assert review_eval["blocking"] is True
    assert any(f["severity"] == "high" and f["category"] == "security_vulnerability" for f in review_eval["findings"])

    # 3. Bare except
    except_code = "def read(path):\n    try:\n        return open(path).read()\n    except:\n        return ''\n"
    review_except = review_code(except_code, "test except")
    assert any(f["severity"] == "medium" and f["category"] == "code_quality" and "Bare exception" in f["title"] for f in review_except["findings"])

    # 4. Pass placeholder in function
    pass_code = "def do_work():\n    pass\n"
    review_pass = review_code(pass_code, "test pass")
    assert any(f["category"] == "placeholder_code" and "Empty implementation" in f["title"] for f in review_pass["findings"])


def test_existing_bobrisknet_behavior_continues_to_work():
    code = "def compute(x: int) -> int:\n    return x * 2\n"
    review = review_code(code, "compute prompt")
    assert "score" in review
    assert isinstance(review["score"], float)
    assert "risk" in review
    assert isinstance(review["risk"], dict)
    assert "score" in review["risk"]


def test_existing_reviewer_api_remains_compatible_with_workflow():
    code = "def clean(): return 1"
    prompt = "Simple prompt"
    test_result = {"passed": True, "duration_ms": 5}

    # Verify calling with 3 arguments like workflow.py does
    review = review_code(code, prompt, test_result)

    # Assert all keys expected by workflow.py
    assert "findings" in review
    assert isinstance(review["findings"], list)
    assert "blocking" in review
    assert isinstance(review["blocking"], bool)
    assert "score" in review
    assert isinstance(review["score"], float)
    assert "risk" in review
    assert isinstance(review["risk"], dict)
    assert "summary" in review
    assert isinstance(review["summary"], str)
    assert "passed" in review
    assert isinstance(review["passed"], bool)

    # Optional 4th argument (tests) works as well
    review_with_tests = review_code(code, prompt, test_result, tests="import unittest\nclass T(unittest.TestCase): pass")
    assert isinstance(review_with_tests["findings"], list)
