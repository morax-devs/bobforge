"""Tests for the dynamic Builder agent and offline template safeguards."""

from unittest.mock import patch

from backend.agents import (
    BUILDER_SYSTEM_PROMPT,
    RECOGNIZED_OFFLINE_TEMPLATES,
    _challenge,
    _detect_template_challenge,
    build_code,
)
from backend.model_client import JsonGenerationResult, ProviderError


def test_recognized_offline_templates_contain_benchmarks():
    assert "fibonacci" in RECOGNIZED_OFFLINE_TEMPLATES
    assert "prime" in RECOGNIZED_OFFLINE_TEMPLATES
    assert "palindrome" in RECOGNIZED_OFFLINE_TEMPLATES
    assert "lru_cache" in RECOGNIZED_OFFLINE_TEMPLATES
    assert "matrix_exponentiation" in RECOGNIZED_OFFLINE_TEMPLATES


def test_detect_template_challenge_matches_benchmarks():
    assert _detect_template_challenge("Build a Fibonacci number generator") == "fibonacci"
    assert _detect_template_challenge("Check if integer is prime") == "prime"
    assert _detect_template_challenge("Implement an LRU Cache with capacity eviction") == "lru_cache"
    assert _detect_template_challenge("Calculate exponentiation of a matrix") == "matrix_exponentiation"


def test_detect_template_challenge_rejects_arbitrary_gui_and_unknown_prompts():
    assert _detect_template_challenge("Build a simple Sudoku game using Python and CustomTkinter") is None
    assert _detect_template_challenge("Create a real-time weather forecasting dashboard") is None
    assert _detect_template_challenge("Build a Flask REST API for inventory management") is None


def test_builder_llm_success_returns_generated_code_and_tests():
    sample_data = {
        "challenge": "calculator",
        "code": "def calculate(a: int, b: int) -> int:\n    return a + b\n",
        "tests": (
            "import unittest\nfrom main import calculate\n\n"
            "class CalcTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(calculate(2, 3), 5)\n"
        ),
    }
    mock_res = JsonGenerationResult(
        data=sample_data,
        provider="anthropic",
        status="success",
        source="anthropic",
        error=None,
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Build an addition calculator")

    assert res["code"] == sample_data["code"].strip()
    assert res["tests"] == sample_data["tests"].strip()
    assert res["challenge"] == "calculator"
    assert res["provider"] == "anthropic"
    assert res["generation_status"] == "success"
    assert res["generation_source"] == "llm"
    assert res["provider_warning"] is None


def test_builder_arbitrary_prompt_with_successful_llm_does_not_use_template():
    custom_sudoku_code = (
        "import customtkinter as ctk\n\n"
        "class SudokuApp:\n"
        "    def __init__(self):\n"
        "        self.grid = [[0]*9 for _ in range(9)]\n"
    )
    custom_sudoku_tests = (
        "import unittest\nfrom main import SudokuApp\n\n"
        "class SudokuTests(unittest.TestCase):\n"
        "    def test_init(self):\n"
        "        app = SudokuApp()\n"
        "        self.assertEqual(len(app.grid), 9)\n"
    )
    mock_res = JsonGenerationResult(
        data={"challenge": "sudoku_gui", "code": custom_sudoku_code, "tests": custom_sudoku_tests},
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Build a simple Sudoku game using Python and CustomTkinter")

    assert res["code"] == custom_sudoku_code.strip()
    assert res["generation_source"] == "llm"
    assert res["generation_status"] == "success"
    assert res["challenge"] == "sudoku_gui"
    # Ensure offline template SudokuGame was NOT used
    assert "SudokuGame" not in res["code"]


def test_builder_provider_failure_on_unknown_prompt_returns_explicit_failure():
    quota_err = ProviderError(
        provider="anthropic",
        category="quota_error",
        message="Anthropic quota error: Credit balance is too low (Error 400).",
        status_code=400,
        retryable=False,
    )
    mock_res = JsonGenerationResult(
        data=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Build a simple Sudoku game using Python and CustomTkinter")

    assert res["generation_status"] == "provider_error"
    assert res["generation_source"] == "failed"
    assert res["challenge"] == "unfulfilled_specification"
    assert "def solve" not in res["code"]
    assert "Anthropic quota error" in res["provider_warning"]
    assert "self.fail" in res["tests"]


def test_builder_offline_unsupported_on_arbitrary_prompt():
    mock_res = JsonGenerationResult(
        data=None,
        provider="offline",
        status="offline",
        source="offline",
        error=None,
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Build a decentralized peer-to-peer file sharing protocol")

    assert res["generation_status"] == "offline_unsupported"
    assert res["generation_source"] == "failed"
    assert res["challenge"] == "unfulfilled_specification"
    assert "def solve" not in res["code"]
    assert "Offline mode only supports recognized benchmark tasks" in res["provider_warning"]
    assert "self.fail" in res["tests"]


def test_builder_recognized_offline_template_works_when_offline():
    mock_res = JsonGenerationResult(
        data=None,
        provider="offline",
        status="offline",
        source="offline",
        error=None,
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Build a Python function that returns the nth Fibonacci number.")

    assert res["generation_status"] == "offline_template"
    assert res["generation_source"] == "offline_template"
    assert res["challenge"] == "fibonacci"
    assert "def fibonacci" in res["code"]
    assert "FibonacciContractTests" in res["tests"]


def test_builder_recognized_offline_template_fallback_on_provider_error():
    quota_err = ProviderError(
        provider="anthropic",
        category="quota_error",
        message="Anthropic quota error: Credit balance is too low (Error 400).",
        status_code=400,
        retryable=False,
    )
    mock_res = JsonGenerationResult(
        data=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Implement a Least Recently Used (LRU) Cache with capacity eviction and O(1) lookups.")

    assert res["generation_status"] == "offline_template"
    assert res["generation_source"] == "offline_template"
    assert res["challenge"] == "lru_cache"
    assert "class LRUCache" in res["code"]
    assert "Anthropic quota error" in (res["provider_warning"] or "")


def test_builder_llm_syntax_error_falls_back_or_fails():
    # LLM returns invalid Python syntax
    mock_res = JsonGenerationResult(
        data={"challenge": "broken", "code": "def broken_func(:\n", "tests": "import unittest\n"},
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    # For unknown prompt -> fails explicitly
    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Build a custom analytics parser")

    assert res["generation_source"] == "failed"
    assert "def solve" not in res["code"]


def test_builder_java_generation_and_offline_template():
    # 1. Test offline Java template for two_sum / benchmark
    mock_offline = JsonGenerationResult(
        data=None,
        provider="offline",
        status="offline",
        source="offline",
        error=None,
    )
    with patch("backend.agents.CLIENT.generate_json", return_value=mock_offline):
        res_java = build_code("Given an array of integers nums and an integer target, return indices of two numbers that add up to target.", language="java")

    assert "class Solution" in res_java["code"]
    assert "public int[] twoSum" in res_java["code"]
    assert "import java.util.*;" in res_java["code"]
    assert "def " not in res_java["code"]
    assert res_java["generation_source"] == "offline_template"


def test_builder_cpp_generation_and_offline_template():
    # 1. Test offline C++ template for two_sum / benchmark
    mock_offline = JsonGenerationResult(
        data=None,
        provider="offline",
        status="offline",
        source="offline",
        error=None,
    )
    with patch("backend.agents.CLIENT.generate_json", return_value=mock_offline):
        res_cpp = build_code("Given an array of integers nums and an integer target, return indices of two numbers that add up to target.", language="cpp")

    assert "class Solution" in res_cpp["code"]
    assert "vector<int>" in res_cpp["code"]
    assert "#include <vector>" in res_cpp["code"]
    assert "def " not in res_cpp["code"]
    assert res_cpp["generation_source"] == "offline_template"


def test_builder_java_llm_generation_validates_without_python_ast():
    java_code = """import java.util.*;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (map.containsKey(complement)) {
                return new int[] { map.get(complement), i };
            }
            map.put(nums[i], i);
        }
        return new int[0];
    }
}"""
    mock_res = JsonGenerationResult(
        data={"challenge": "two_sum", "code": java_code, "tests": "// Test Java suite"},
        provider="gemini",
        status="success",
        source="gemini",
    )
    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = build_code("Two sum problem", language="java")

    assert res["generation_source"] == "llm"
    assert "public int[] twoSum" in res["code"]
    assert "def " not in res["code"]

