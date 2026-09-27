"""End-to-End integration tests validating the complete BobForge backend pipeline.

Exercises the full loop:
User Prompt -> Builder -> Reviewer (AST + BobRiskNet + Semantic) -> Runner (sandbox subprocess)
-> (if needed) Fixer -> Reviewer -> Runner -> Finisher
"""

from unittest.mock import patch
import pytest

from backend.agents import review_code
from backend.model_client import GenerationResult, JsonGenerationResult, ProviderError
from backend.workflow import run_workflow


def test_scenario_1_simple_arbitrary_algorithm_binary_search():
    """Scenario 1: Simple Arbitrary Algorithm (Binary Search).
    Validates dynamic generation, semantic review, real sandbox test execution, and completion.
    """
    prompt = "Implement binary search in Python for a sorted list. Return the index of the target or -1 if it is not present."
    bs_code = '''"""Binary search algorithm."""
from typing import List, Any

def binary_search(arr: List[Any], target: Any) -> int:
    """Perform binary search returning index or -1."""
    if not isinstance(arr, list):
        raise TypeError("arr must be a list")
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
'''
    bs_tests = '''import unittest
from main import binary_search

class BinarySearchTests(unittest.TestCase):
    def test_found(self):
        self.assertEqual(binary_search([1, 3, 5, 7, 9], 5), 2)
        self.assertEqual(binary_search([1, 3, 5, 7, 9], 1), 0)
        self.assertEqual(binary_search([1, 3, 5, 7, 9], 9), 4)

    def test_not_found(self):
        self.assertEqual(binary_search([1, 3, 5, 7, 9], 2), -1)
        self.assertEqual(binary_search([], 5), -1)

    def test_type_validation(self):
        with self.assertRaises(TypeError):
            binary_search("not a list", 5)
'''
    mock_builder_res = JsonGenerationResult(
        data={"challenge": "binary_search", "code": bs_code, "tests": bs_tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_reviewer_res = JsonGenerationResult(
        data={"passed": True, "summary": "Valid binary search implementation.", "findings": []},
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_res, mock_reviewer_res]):
        result = run_workflow(prompt)

    assert result["status"] == "completed"
    assert result["test_result"]["passed"] is True
    assert result["test_result"]["passed_count"] == 3
    assert result["test_result"]["total_count"] == 3
    assert result["iterations"] == 0
    assert result["generation_source"] == "llm"
    assert "def binary_search" in result["code"]
    assert "Ready to ship" in result["message"]


def test_scenario_2_lru_cache_dynamic_generation():
    """Scenario 2: LRU Cache (dynamic arbitrary generation, not relying on offline template).
    Exercises real cache behavior in sandbox test runner.
    """
    prompt = "Implement an LRU cache with a fixed capacity supporting get and put operations."
    lru_code = '''"""Dynamic LRU Cache implementation."""
from typing import Any

class LRUCache:
    def __init__(self, capacity: int):
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("Capacity must be positive integer")
        self.capacity = capacity
        self.data = {}

    def get(self, key: Any) -> Any:
        if key not in self.data:
            return -1
        val = self.data.pop(key)
        self.data[key] = val
        return val

    def put(self, key: Any, value: Any) -> None:
        if key in self.data:
            self.data.pop(key)
        elif len(self.data) >= self.capacity:
            oldest_key = next(iter(self.data))
            del self.data[oldest_key]
        self.data[key] = value
'''
    lru_tests = '''import unittest
from main import LRUCache

class CustomLRUTests(unittest.TestCase):
    def test_lru_operations(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        cache.put("c", 3)
        self.assertEqual(cache.get("b"), -1)
        self.assertEqual(cache.get("c"), 3)

    def test_validation(self):
        with self.assertRaises(ValueError):
            LRUCache(0)
'''
    mock_builder_res = JsonGenerationResult(
        data={"challenge": "dynamic_lru", "code": lru_code, "tests": lru_tests},
        provider="granite",
        status="success",
        source="granite",
    )
    mock_reviewer_res = JsonGenerationResult(
        data={"passed": True, "summary": "Valid LRU cache implementation.", "findings": []},
        provider="granite",
        status="success",
        source="granite",
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_res, mock_reviewer_res]):
        result = run_workflow(prompt)

    assert result["test_result"]["passed"] is True
    assert result["test_result"]["passed_count"] == 2
    assert result["generation_source"] == "llm"
    assert result["provider"] == "granite"
    assert "oldest_key = next(iter(self.data))" in result["code"]
    assert "Ready to ship" in result["message"]


def test_scenario_3_dijkstra_dynamic_generation():
    """Scenario 3: Dijkstra algorithm dynamic generation.
    Tests priority queue algorithm and graph distance relaxations in real sandbox.
    """
    prompt = "Implement Dijkstra's shortest path algorithm for a weighted graph and return shortest distances from a source node."
    dijkstra_code = '''"""Dijkstra algorithm."""
import heapq
from typing import Dict, List, Tuple, Any

def dijkstra(graph: Dict[Any, List[Tuple[Any, float]]], source: Any) -> Dict[Any, float]:
    """Calculate shortest paths using Dijkstra."""
    if not isinstance(graph, dict):
        raise TypeError("Graph must be a dictionary")
    if source not in graph and len(graph) > 0:
        raise ValueError("Source node not in graph")
    distances = {node: float("inf") for node in graph}
    distances[source] = 0.0
    pq = [(0.0, source)]
    while pq:
        curr_dist, u = heapq.heappop(pq)
        if curr_dist > distances[u]:
            continue
        for v, weight in graph.get(u, []):
            if weight < 0:
                raise ValueError("Negative weights unsupported")
            if curr_dist + weight < distances[v]:
                distances[v] = curr_dist + weight
                heapq.heappush(pq, (distances[v], v))
    return distances
'''
    dijkstra_tests = '''import unittest
from main import dijkstra

class DijkstraTests(unittest.TestCase):
    def test_shortest_path(self):
        g = {"A": [("B", 1.0), ("C", 4.0)], "B": [("C", 2.0)], "C": []}
        d = dijkstra(g, "A")
        self.assertEqual(d["A"], 0.0)
        self.assertEqual(d["B"], 1.0)
        self.assertEqual(d["C"], 3.0)

    def test_validation(self):
        with self.assertRaises(TypeError):
            dijkstra("not_a_dict", "A")
'''
    mock_builder_res = JsonGenerationResult(
        data={"challenge": "dijkstra_dynamic", "code": dijkstra_code, "tests": dijkstra_tests},
        provider="openai",
        status="success",
        source="openai",
    )
    mock_reviewer_res = JsonGenerationResult(
        data={"passed": True, "summary": "Valid Dijkstra algorithm implementation.", "findings": []},
        provider="openai",
        status="success",
        source="openai",
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_res, mock_reviewer_res]):
        result = run_workflow(prompt)

    assert result["test_result"]["passed"] is True
    assert result["test_result"]["passed_count"] == 2
    assert "heapq.heappop" in result["code"]
    assert "Ready to ship" in result["message"]


def test_scenario_4_gui_application_sudoku_customtkinter():
    """Scenario 4: GUI Application (Sudoku with CustomTkinter).
    Verifies that GUI architecture is preserved, headless-safe logic is tested,
    and no generic placeholder or CLI template replacement is accepted.
    """
    prompt = "Build a simple Sudoku game using Python and CustomTkinter."
    sudoku_code = '''"""Sudoku game with CustomTkinter GUI."""
try:
    import customtkinter as ctk
except ImportError:
    ctk = None

class SudokuEngine:
    """Headless game logic for board representation and move validation."""
    def __init__(self):
        self.grid = [[0 for _ in range(9)] for _ in range(9)]

    def set_cell(self, row: int, col: int, val: int) -> bool:
        if not (0 <= row < 9 and 0 <= col < 9 and 1 <= val <= 9):
            raise ValueError("Invalid coordinates or value")
        for i in range(9):
            if self.grid[row][i] == val or self.grid[i][col] == val:
                return False
        self.grid[row][col] = val
        return True

class SudokuGUI:
    """CustomTkinter GUI application."""
    def __init__(self, master=None):
        self.engine = SudokuEngine()
        self.master = master
        self.cells = {}

    def build_grid(self):
        if ctk and self.master:
            for r in range(9):
                for c in range(9):
                    btn = ctk.CTkButton(self.master, text="", width=40, height=40)
                    self.cells[(r, c)] = btn
'''
    sudoku_tests = '''import unittest
from main import SudokuEngine, SudokuGUI

class SudokuHeadlessTests(unittest.TestCase):
    def test_engine_move_validation(self):
        engine = SudokuEngine()
        self.assertTrue(engine.set_cell(0, 0, 5))
        self.assertFalse(engine.set_cell(0, 1, 5))

    def test_gui_initialization_headless(self):
        gui = SudokuGUI(master=None)
        self.assertIsNotNone(gui.engine)
        self.assertEqual(len(gui.cells), 0)

    def test_invalid_input(self):
        engine = SudokuEngine()
        with self.assertRaises(ValueError):
            engine.set_cell(10, 0, 5)
'''
    mock_builder_res = JsonGenerationResult(
        data={"challenge": "sudoku_customtkinter", "code": sudoku_code, "tests": sudoku_tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_reviewer_res = JsonGenerationResult(
        data={
            "passed": True,
            "summary": "CustomTkinter GUI structure and headless SudokuEngine verified cleanly.",
            "findings": [],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_res, mock_reviewer_res]):
        result = run_workflow(prompt)

    assert result["test_result"]["passed"] is True
    assert result["test_result"]["passed_count"] == 3
    assert "class SudokuGUI" in result["code"]
    assert "class SudokuEngine" in result["code"]
    assert "customtkinter" in result["code"]
    assert "SudokuGame" not in result["code"]  # offline CLI template was NOT used


def test_scenario_5_deliberately_bad_generated_code_repair_loop():
    """Scenario 5: Deliberately Bad Generated Code (Repair Loop).
    Builder returns intentionally faulty code -> tests fail -> Fixer receives
    actual telemetry & review findings -> produces corrected code -> tests pass.
    """
    prompt = "Implement a function that validates email addresses and rejects malformed input."
    buggy_email_code = '''"""Email validator."""
def validate_email(email: str) -> bool:
    # Deliberate bug: accepts everything
    return True
'''
    email_tests = '''import unittest
from main import validate_email

class EmailValidatorContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_email("user@example.com"))

    def test_reject_missing_at(self):
        self.assertFalse(validate_email("invalid-email"))

    def test_reject_empty(self):
        self.assertFalse(validate_email(""))
'''
    fixed_email_code = '''"""Email validator."""
import re

def validate_email(email: str) -> bool:
    """Validate RFC email address syntax."""
    if not isinstance(email, str) or not email or len(email) > 254:
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))
'''
    mock_builder_res = JsonGenerationResult(
        data={"challenge": "email_validator", "code": buggy_email_code, "tests": email_tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_rev_0 = JsonGenerationResult(
        data={"passed": True, "summary": "Initial static check clear.", "findings": []},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_fixer_res = JsonGenerationResult(
        data={
            "code": fixed_email_code,
            "rationale": "Replaced return True with regex validation matching email syntax rules.",
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_rev_1 = JsonGenerationResult(
        data={"passed": True, "summary": "Repaired email validator passes review.", "findings": []},
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_res, mock_rev_0, mock_fixer_res, mock_rev_1]):
        result = run_workflow(prompt)

    assert result["test_result"]["passed"] is True
    assert result["test_result"]["passed_count"] == 3
    assert result["iterations"] == 1
    assert "re.match(pattern, email)" in result["code"]
    assert any(e["agent"] == "Fixer" for e in result["events"])
    assert "Ready to ship" in result["message"]


def test_scenario_6_semantic_mismatch_triggers_fixer():
    """Scenario 6: Semantic Mismatch.
    Builder returns unrelated code (Fibonacci instead of Sudoku) -> tests pass
    syntactically -> Reviewer detects semantic mismatch -> Fixer receives findings
    and synthesizes real Sudoku -> Reviewer passes -> pipeline completes.
    """
    prompt = "Build a Sudoku game using Python and CustomTkinter."
    unrelated_fib_code = '''"""Fibonacci sequence."""
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
'''
    unrelated_tests = '''import unittest
from main import fibonacci

class FibTests(unittest.TestCase):
    def test_fib(self):
        self.assertEqual(fibonacci(1), 1)
'''
    repaired_sudoku_code = '''"""Sudoku game using CustomTkinter."""
class SudokuGame:
    def __init__(self):
        self.grid = [[0]*9 for _ in range(9)]
'''
    repaired_sudoku_tests = '''import unittest
from main import SudokuGame

class SudokuContractTests(unittest.TestCase):
    def test_board_init(self):
        game = SudokuGame()
        self.assertEqual(len(game.grid), 9)
'''
    mock_builder_res = JsonGenerationResult(
        data={"challenge": "unrelated", "code": unrelated_fib_code, "tests": unrelated_tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_rev_mismatch = JsonGenerationResult(
        data={
            "passed": False,
            "summary": "Code implements Fibonacci instead of the requested Sudoku game and CustomTkinter GUI.",
            "findings": [
                {
                    "category": "semantic_mismatch",
                    "severity": "high",
                    "title": "Severe semantic mismatch",
                    "message": "The generated code implements Fibonacci numbers rather than a Sudoku game.",
                    "evidence": "def fibonacci(n)",
                    "fix": "Implement SudokuGame class.",
                    "line": 2,
                }
            ],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_fixer_res = JsonGenerationResult(
        data={
            "code": repaired_sudoku_code,
            "tests": repaired_sudoku_tests,
            "rationale": "Replaced unrelated Fibonacci implementation with SudokuGame and contract tests.",
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_rev_pass = JsonGenerationResult(
        data={"passed": True, "summary": "Sudoku implementation satisfied.", "findings": []},
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_res, mock_rev_mismatch, mock_fixer_res, mock_rev_pass]):
        result = run_workflow(prompt)

    assert result["iterations"] >= 1
    assert "SudokuGame" in result["code"]
    assert "fibonacci" not in result["code"]


def test_scenario_7_provider_failure_handling():
    """Scenario 7: Provider Failure Handling.
    Part A: Provider failure during Builder -> reports failure clearly, no solve() fallback, no fake pass.
    Part B: Provider failure during Fixer -> original code preserved, repair failed, no false success.
    """
    prompt = "Build a distributed vector database"

    quota_err = ProviderError(
        provider="anthropic",
        category="quota_error",
        message="Anthropic quota error: Credit balance is too low (Error 400).",
        status_code=400,
    )
    mock_fail_res = JsonGenerationResult(
        data=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )

    # Part A: Builder failure
    raw_fail_res = GenerationResult(
        text="",
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )
    with patch("backend.agents.CLIENT.generate_json", return_value=mock_fail_res), \
         patch("backend.agents.CLIENT.generate", return_value=raw_fail_res):
        result = run_workflow(prompt)

    assert result["test_result"]["passed"] is False
    assert result["challenge"] == "unfulfilled_specification"
    assert "def solve" not in result["code"]
    assert "Generation Failed" in result["code"]
    assert "Anthropic quota error" in str(result["provider_warning"])
    assert "Ready to ship" not in result["message"]

    # Part B: Fixer failure
    buggy_code = "def calc(): return 0"
    failing_tests = '''import unittest
from main import calc
class T(unittest.TestCase):
    def test_one(self): self.assertEqual(calc(), 1)
'''
    mock_builder_ok = JsonGenerationResult(
        data={"challenge": "calc", "code": buggy_code, "tests": failing_tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_rev_ok = JsonGenerationResult(
        data={"passed": True, "summary": "Code clean", "findings": []},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_fix_fail = JsonGenerationResult(
        data=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )
    mock_raw_fail = GenerationResult(
        text=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder_ok, mock_rev_ok, mock_fix_fail, mock_rev_ok, mock_fix_fail, mock_rev_ok]), \
         patch("backend.agents.CLIENT.generate", return_value=mock_raw_fail):
        result2 = run_workflow("Build a calculator returning 1", max_iterations=2)

    assert result2["test_result"]["passed"] is False
    assert result2["code"] == buggy_code  # original code preserved
    assert "Ready to ship" not in result2["message"]


def test_scenario_8_multi_iteration_repair_and_budget_exhaustion():
    """Scenario 8: Multi-Iteration Repair.
    Verifies that the workflow performs multiple Reviewer/Runner cycles and respects iteration budget.
    """
    prompt = "Build a number parser with multiple validation checks"
    code_v0 = "def parse_num(s): return 0"
    tests = '''import unittest
from main import parse_num

class ParseTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_num("42"), 42)
    def test_float_string(self):
        self.assertEqual(parse_num("3.14"), 3)
    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_num("abc")
'''
    code_v1 = "def parse_num(s): return int(s)"
    code_v2 = '''def parse_num(s):
    try:
        return int(float(s)) if '.' in s else int(s)
    except Exception as e:
        raise ValueError("Invalid number string") from e
'''
    mock_builder = JsonGenerationResult(
        data={"challenge": "num_parser", "code": code_v0, "tests": tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    mock_rev = JsonGenerationResult(data={"passed": True, "summary": "ok", "findings": []}, provider="anthropic", status="success", source="anthropic")
    mock_fix1 = JsonGenerationResult(data={"code": code_v1, "rationale": "Handle float strings"}, provider="anthropic", status="success", source="anthropic")
    mock_fix2 = JsonGenerationResult(data={"code": code_v2, "rationale": "Handle invalid strings with ValueError"}, provider="anthropic", status="success", source="anthropic")

    with patch("backend.agents.CLIENT.generate_json", side_effect=[mock_builder, mock_rev, mock_fix1, mock_rev, mock_fix2, mock_rev]):
        result = run_workflow(prompt, max_iterations=3)

    assert result["test_result"]["passed"] is True
    assert result["iterations"] == 2
    assert "Ready to ship" in result["message"]


def test_no_false_positives_enforcement():
    """Explicitly verify that placeholders, empty pass, semantic mismatch,
    and provider errors NEVER produce successful completion.
    """
    # 1. Generic solve() placeholder is flagged by semantic reviewer
    mock_rev_reject = JsonGenerationResult(
        data={
            "passed": False,
            "summary": "Generic solve() placeholder rejected",
            "findings": [{"category": "placeholder_code", "severity": "high", "title": "Placeholder stub"}],
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )
    with patch("backend.agents.CLIENT.get_active_provider_info", return_value={"mode": "anthropic", "active": "anthropic"}), \
         patch("backend.agents.CLIENT.generate_json", return_value=mock_rev_reject):
        rev = review_code("def solve(x): return x", "Build a weather app")
    assert rev["passed"] is False
    assert rev["blocking"] is True

    # 2. Empty pass implementation flagged by AST
    rev_pass = review_code("def run():\n    pass\n", "Run prompt")
    assert any(f["category"] == "placeholder_code" for f in rev_pass["findings"])

    # 3. Provider failure never produces successful workflow
    with patch("backend.agents.CLIENT._get_provider_chain", return_value=[]):
        failed_workflow = run_workflow("Build an arbitrary tool that does X", max_iterations=1)
    assert failed_workflow["test_result"].get("passed") is not True
    assert "Ready to ship" not in failed_workflow["message"]
