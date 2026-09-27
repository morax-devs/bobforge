"""Comprehensive tests for Phase 4 dynamic Fixer: LLM repair, telemetry consumption, and failure handling."""

from unittest.mock import MagicMock, patch

from backend.agents import FIXER_SYSTEM_PROMPT, fix_code
from backend.model_client import GenerationResult, JsonGenerationResult, ProviderError


def test_arbitrary_implementation_semantic_reviewer_failure_repaired_dynamically():
    prompt = "Build a binary search algorithm for sorted lists returning the target index or -1."
    buggy_code = """def binary_search(arr, target):
    # Dummy broken return
    return 0
"""
    review = {
        "findings": [
            {
                "category": "semantic_mismatch",
                "severity": "high",
                "title": "Broken search logic",
                "message": "Function always returns 0 instead of performing binary search.",
                "evidence": "return 0",
                "fix": "Implement left, right pointers and mid element search.",
                "line": 3,
            }
        ],
        "blocking": True,
    }
    test_result = {
        "passed": False,
        "failing_tests": ["test_not_found"],
        "assertion_error": "AssertionError: 0 != -1",
        "traceback_snippet": "File test_main.py, line 8 in test_not_found",
    }

    repaired_code = """def binary_search(arr, target):
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
"""
    mock_res = JsonGenerationResult(
        data={
            "code": repaired_code,
            "rationale": "Implemented standard binary search loop with proper index updates.",
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(buggy_code, review, test_result, prompt)

    assert res["success"] is True
    assert res["repair_status"] == "success"
    assert res["repair_source"] == "llm"
    assert "while left <= right:" in res["code"]
    assert res["provider"] == "anthropic"


def test_runtime_traceback_supplied_and_used_in_repair_request():
    prompt = "Build an email validator"
    code = "def validate_email(email): raise KeyError('not implemented')"
    review = {"findings": []}
    test_result = {
        "passed": False,
        "failing_tests": ["test_valid_email"],
        "assertion_error": "KeyError: 'not implemented'",
        "traceback_snippet": "Traceback (most recent call last):\n  File 'test_main.py', line 12, in test_valid_email",
        "output": "Test stdout telemetry",
        "error": "Test stderr telemetry",
    }

    captured_prompt = None

    def fake_generate_json(user_prompt, system=None, temperature=0.1):
        nonlocal captured_prompt
        captured_prompt = user_prompt
        return JsonGenerationResult(
            data={"code": "def validate_email(email): return True", "rationale": "Fixed KeyError"},
            provider="anthropic",
            status="success",
            source="anthropic",
        )

    with patch("backend.agents.CLIENT.generate_json", side_effect=fake_generate_json):
        res = fix_code(code, review, test_result, prompt)

    assert res["success"] is True
    assert captured_prompt is not None
    assert "KeyError: 'not implemented'" in captured_prompt
    assert "test_valid_email" in captured_prompt
    assert "Traceback (most recent call last):" in captured_prompt
    assert "Test stdout telemetry" in captured_prompt


def test_reviewer_findings_supplied_in_repair_request():
    prompt = "Build a simple Sudoku game using Python and CustomTkinter"
    code = "def solve(input_data): return input_data"
    review = {
        "findings": [
            {
                "category": "placeholder_code",
                "severity": "high",
                "title": "Placeholder solve() detected",
                "message": "The implementation does not provide a Sudoku board or CustomTkinter GUI.",
                "evidence": "def solve(input_data): return input_data",
                "fix": "Implement SudokuGame class and GUI.",
                "line": 1,
            }
        ]
    }
    test_result = {"passed": True}

    captured_prompt = None

    def fake_generate_json(user_prompt, system=None, temperature=0.1):
        nonlocal captured_prompt
        captured_prompt = user_prompt
        return JsonGenerationResult(
            data={"code": "class SudokuGame:\n    pass\n", "rationale": "Created SudokuGame class"},
            provider="granite",
            status="success",
            source="granite",
        )

    with patch("backend.agents.CLIENT.generate_json", side_effect=fake_generate_json):
        res = fix_code(code, review, test_result, prompt)

    assert res["success"] is True
    assert captured_prompt is not None
    assert "placeholder_code" in captured_prompt
    assert "Placeholder solve() detected" in captured_prompt
    assert "Implement SudokuGame class and GUI" in captured_prompt


def test_incorrect_arbitrary_algorithm_receives_llm_repair():
    prompt = "Build Dijkstra's shortest path algorithm for weighted directed graphs."
    code = "def dijkstra(graph, start): return {}"
    review = {
        "findings": [
            {"category": "missing_requirement", "severity": "high", "message": "Returns empty dict without computing paths"}
        ]
    }
    test_result = {
        "passed": False,
        "failing_tests": ["test_shortest_path"],
        "assertion_error": "AssertionError: {} != {'A': 0.0, 'B': 1.0}",
    }

    mock_res = JsonGenerationResult(
        data={
            "code": "import heapq\ndef dijkstra(graph, start):\n    distances = {start: 0.0}\n    return distances\n",
            "rationale": "Implemented Dijkstra with distances dictionary.",
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(code, review, test_result, prompt)

    assert res["success"] is True
    assert "distances = {start: 0.0}" in res["code"]
    assert "import heapq" in res["code"]


def test_placeholder_implementation_receives_llm_repair():
    prompt = "Build an in-memory TaskList manager"
    code = "def solve(input_data): return input_data"
    review = {"findings": [{"category": "placeholder_code", "severity": "high", "message": "Generic stub"}]}
    test_result = {"passed": False, "failing_tests": ["test_add_task"]}

    mock_res = JsonGenerationResult(
        data={
            "code": "class TaskList:\n    def __init__(self):\n        self._tasks = []\n    def add(self, t):\n        self._tasks.append(t)\n",
            "rationale": "Replaced placeholder with TaskList class.",
        },
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(code, review, test_result, prompt)

    assert res["success"] is True
    assert "class TaskList:" in res["code"]
    assert "def solve" not in res["code"]


def test_no_fibonacci_regex_repair_used_in_normal_path():
    prompt = "Build a Python function that returns the nth Fibonacci number."
    buggy_fib = """def fibonacci(n: int) -> int:
    if n <= 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)
"""
    review = {"findings": [{"category": "logic_error", "message": "Base case returns 1 for n=0"}]}
    test_result = {
        "passed": False,
        "failing_tests": ["test_sequence_start"],
        "assertion_error": "AssertionError: 1 != 0",
    }

    mock_res = JsonGenerationResult(
        data={
            "code": buggy_fib.replace("return 1", "return n"),
            "rationale": "[Custom-LLM-Patch] Updated recursive base case to return n.",
        },
        provider="custom_llm",
        status="success",
        source="custom_llm",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(buggy_fib, review, test_result, prompt)

    assert res["success"] is True
    assert res["repair_source"] == "llm"
    # Ensure it used the LLM rationale and NOT the old regex rationale
    assert "[Custom-LLM-Patch]" in res["rationale"]
    assert "Restored correct base case: return n for n <= 1 (fibonacci(0) = 0)." not in res["rationale"]


def test_llm_provider_failure_produces_explicit_repair_failure():
    prompt = "Build a calculator"
    code = "def calc(): return 'broken'"
    review = {"findings": []}
    test_result = {"passed": False, "failing_tests": ["test_calc"]}

    quota_err = ProviderError(
        provider="anthropic",
        category="quota_error",
        message="Anthropic quota error: Credit balance is too low (Error 400).",
        status_code=400,
    )
    failed_json_res = JsonGenerationResult(
        data=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )
    failed_raw_res = GenerationResult(
        text=None,
        provider="anthropic",
        status="provider_error",
        source="anthropic",
        error=quota_err,
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=failed_json_res), \
         patch("backend.agents.CLIENT.generate", return_value=failed_raw_res):
        res = fix_code(code, review, test_result, prompt)

    assert res["success"] is False
    assert res["repair_status"] == "provider_error"
    assert res["repair_source"] == "failed"
    assert res["code"] == code  # Original code preserved!
    assert "Anthropic quota error" in res["rationale"]
    assert res["error"] == quota_err.message


def test_existing_fixer_api_compatibility_with_workflow():
    prompt = "Sample task"
    code = "def sample(): return 1"
    review = {"findings": []}
    test_result = {"passed": True}

    mock_res = JsonGenerationResult(
        data={"code": code, "rationale": "Verified code"},
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(code, review, test_result, prompt)

    # workflow.py line 140-141 expects 'code' and 'rationale'
    assert "code" in res
    assert "rationale" in res
    assert isinstance(res["code"], str)
    assert isinstance(res["rationale"], str)


def test_existing_tests_not_weakened_directive():
    # Verify FIXER_SYSTEM_PROMPT explicitly forbids weakening/removing assertions
    assert "NEVER weaken, bypass, or delete assertions" in FIXER_SYSTEM_PROMPT
    assert "satisfy Reviewer findings" in FIXER_SYSTEM_PROMPT or "Root-Cause Repair" in FIXER_SYSTEM_PROMPT


def test_structured_repair_metadata_preserved():
    prompt = "Build a string reverser"
    code = "def reverse_str(s): return s[::-1]"
    review = {"findings": []}
    test_result = {"passed": True}

    mock_res = JsonGenerationResult(
        data={"code": code, "rationale": "Validated reverse_str."},
        provider="openai",
        status="success",
        source="openai",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(code, review, test_result, prompt)

    assert "code" in res
    assert "tests" in res
    assert "rationale" in res
    assert "success" in res
    assert "provider" in res
    assert "repair_status" in res
    assert "repair_source" in res
    assert res["success"] is True
    assert res["provider"] == "openai"
    assert res["repair_status"] == "success"
    assert res["repair_source"] == "llm"


def test_fixer_preserves_java_code_and_does_not_convert_to_python():
    java_buggy = """import java.util.*;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        return null; // Buggy stub
    }
}"""
    java_repaired = """import java.util.*;

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
        data={"code": java_repaired, "rationale": "Implemented hash table lookup in Java."},
        provider="gemini",
        status="success",
        source="gemini",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(
            java_buggy,
            {"findings": [{"category": "placeholder_code", "severity": "high", "fix": "Implement hash table"}]},
            {"passed": False, "assertion_error": "NullPointerException"},
            "Solve Two Sum in Java",
            language="java",
        )

    assert res["success"] is True
    assert "class Solution" in res["code"]
    assert "public int[] twoSum" in res["code"]
    assert "def " not in res["code"]


def test_fixer_preserves_cpp_code_and_does_not_convert_to_python():
    cpp_buggy = """#include <vector>
using namespace std;

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        return {}; // Buggy stub
    }
};"""
    cpp_repaired = """#include <vector>
#include <unordered_map>
using namespace std;

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> map;
        for (int i = 0; i < nums.size(); ++i) {
            int complement = target - nums[i];
            if (map.count(complement)) {
                return {map[complement], i};
            }
            map[nums[i]] = i;
        }
        return {};
    }
};"""
    mock_res = JsonGenerationResult(
        data={"code": cpp_repaired, "rationale": "Implemented hash map lookup in C++."},
        provider="gemini",
        status="success",
        source="gemini",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res):
        res = fix_code(
            cpp_buggy,
            {"findings": [{"category": "placeholder_code", "severity": "high", "fix": "Implement hash map"}]},
            {"passed": False, "assertion_error": "Empty vector returned"},
            "Solve Two Sum in C++",
            language="cpp",
        )

    assert res["success"] is True
    assert "class Solution" in res["code"]
    assert "vector<int>" in res["code"]
    assert "def " not in res["code"]


def test_fixer_rejects_llm_converting_java_to_python():
    java_buggy = "class Solution { public int solve() { return 0; } }"
    python_mistake = "def solve():\n    return 0\n"

    mock_res = JsonGenerationResult(
        data={"code": python_mistake, "rationale": "Rewrote in Python"},
        provider="gemini",
        status="success",
        source="gemini",
    )

    with patch("backend.agents.CLIENT.generate_json", return_value=mock_res), patch("backend.agents.CLIENT.generate", return_value=GenerationResult(text=python_mistake, provider="gemini", status="success", source="gemini")):
        res = fix_code(
            java_buggy,
            {"findings": [{"category": "logic_error", "severity": "high"}]},
            {"passed": False, "assertion_error": "Wrong answer"},
            "Solve in Java",
            language="java",
        )

    # Must reject conversion to Python and preserve original Java code
    assert res["success"] is False
    assert res["code"] == java_buggy
    assert "def " not in res["code"]

