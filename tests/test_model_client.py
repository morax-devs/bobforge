"""Focused tests for model client error handling, classification, and failover in BobForge."""

import io
from urllib import error
import pytest

from backend.model_client import (
    GenerationResult,
    JsonGenerationResult,
    ProviderError,
    UniversalModelClient,
    classify_http_error,
    classify_network_error,
    sanitize_secret,
)


def test_sanitize_secret_removes_known_and_patterned_keys():
    known_key = "sk-ant-api03-abcdef1234567890abcdef1234567890"
    raw_error = f"Error calling endpoint with key {known_key} and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    sanitized = sanitize_secret(raw_error, secrets=[known_key])

    assert known_key not in sanitized
    assert "sk-ant-" not in sanitized
    assert "eyJhbG" not in sanitized
    assert "[REDACTED]" in sanitized


def test_classify_quota_error():
    body = b'{"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API."}}'
    http_err = error.HTTPError("https://api.anthropic.com", 400, "Bad Request", {}, io.BytesIO(body))

    classified = classify_http_error("anthropic", http_err, secrets=["secret-token"])

    assert classified.category == "quota_error"
    assert classified.status_code == 400
    assert "Credit balance is too low" in classified.message
    assert classified.fallback_appropriate is True
    assert classified.retryable is False


def test_classify_authentication_error():
    body = b'{"error":{"message":"Incorrect API key provided: sk-proj-12345."}}'
    http_err = error.HTTPError("https://api.openai.com", 401, "Unauthorized", {}, io.BytesIO(body))

    classified = classify_http_error("openai", http_err, secrets=["sk-proj-12345"])

    assert classified.category == "authentication_error"
    assert classified.status_code == 401
    assert "sk-proj-12345" not in classified.message
    assert "authentication failed" in classified.message.lower()


def test_classify_rate_limit_error():
    body = b'{"error":{"message":"Rate limit reached for requests per minute."}}'
    http_err = error.HTTPError("https://api.groq.com", 429, "Too Many Requests", {}, io.BytesIO(body))

    classified = classify_http_error("groq", http_err)

    assert classified.category == "rate_limit_error"
    assert classified.status_code == 429
    assert classified.retryable is True


def test_classify_server_error():
    body = b'503 Service Unavailable'
    http_err = error.HTTPError("https://us-south.ml.cloud.ibm.com", 503, "Service Unavailable", {}, io.BytesIO(body))

    classified = classify_http_error("ibm-watsonx", http_err)

    assert classified.category == "server_error"
    assert classified.status_code == 503
    assert classified.retryable is True


def test_classify_network_timeout():
    exc = TimeoutError("The read operation timed out")
    classified = classify_network_error("anthropic", exc)

    assert classified.category == "network_connection_error"
    assert classified.retryable is True
    assert "timed out" in classified.message


def test_generation_result_tuple_unpacking_compatibility():
    res = GenerationResult(
        text="def solve(): pass",
        provider="anthropic",
        status="success",
        source="anthropic",
    )

    # Must unpack seamlessly as a 2-tuple: text, provider
    text, provider = res
    assert text == "def solve(): pass"
    assert provider == "anthropic"

    # Properties must be directly accessible
    assert res.status == "success"
    assert res.source == "anthropic"


def test_json_generation_result_tuple_unpacking_compatibility():
    res = JsonGenerationResult(
        data={"code": "pass"},
        provider="groq",
        status="fallback_success",
        source="groq",
    )

    data, provider = res
    assert data == {"code": "pass"}
    assert provider == "groq"
    assert res.status == "fallback_success"


def test_offline_mode_distinct_from_llm():
    client = UniversalModelClient()
    # Force offline chain
    client._get_provider_chain = lambda: []

    result = client.generate("Build a utility function")

    assert result.status == "offline"
    assert result.source == "offline"
    assert result.provider == "offline"
    assert result.text is None


def test_provider_failure_is_not_reported_as_success():
    client = UniversalModelClient()

    class FailingProvider:
        name = "mock_failing_llm"

        def generate_with_error(self, prompt, system="", temperature=0.1):
            return None, ProviderError(
                provider="mock_failing_llm",
                category="quota_error",
                message="Mock provider quota exhausted.",
                status_code=400,
                retryable=False,
                fallback_appropriate=True,
            )

    client._get_provider_chain = lambda: [FailingProvider()]

    result = client.generate("Build something")

    # MUST be provider_error, NEVER success or offline masquerade
    assert result.status == "provider_error"
    assert result.text is None
    assert result.provider == "mock_failing_llm"
    assert result.error is not None
    assert result.error.category == "quota_error"
    assert "quota exhausted" in result.error.message
    assert client.last_error == "Mock provider quota exhausted."


def test_fallback_success_records_audit_trail():
    client = UniversalModelClient()

    class FailingPrimary:
        name = "primary_llm"

        def generate_with_error(self, prompt, system="", temperature=0.1):
            return None, ProviderError(
                provider="primary_llm",
                category="quota_error",
                message="Primary quota exhausted.",
                status_code=400,
                retryable=False,
                fallback_appropriate=True,
            )

    class WorkingSecondary:
        name = "secondary_llm"

        def generate_with_error(self, prompt, system="", temperature=0.1):
            return "def recovered(): return True", None

    client._get_provider_chain = lambda: [FailingPrimary(), WorkingSecondary()]

    result = client.generate("Build something")

    assert result.status == "fallback_success"
    assert result.provider == "secondary_llm"
    assert result.text == "def recovered(): return True"
    assert len(result.attempts) == 2
    assert result.attempts[0]["provider"] == "primary_llm"
    assert result.attempts[0]["success"] is False
    assert result.attempts[0]["category"] == "quota_error"
    assert result.attempts[1]["provider"] == "secondary_llm"
    assert result.attempts[1]["success"] is True
