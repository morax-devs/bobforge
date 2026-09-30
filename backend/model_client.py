"""Universal, provider-independent model client for BobForge.

Supports:
1. Anthropic (Claude 3.5 Sonnet / Haiku)
2. IBM watsonx.ai (Granite code / instruct models)
3. OpenAI-compatible APIs (OpenAI, Groq, OpenRouter, Ollama)
4. Offline deterministic fallback with structured error diagnostics
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
import sys
import time
from typing import Any
from urllib import error, parse, request
from pathlib import Path

# Load .env if present
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


# ==============================================================================
# 1. SECRET SANITIZATION & ERROR CLASSIFICATION
# ==============================================================================

def sanitize_secret(text: str, secrets: list[str] | None = None) -> str:
    """Strip API keys, authorization tokens, and credentials from error text."""
    if not text:
        return ""
    sanitized = str(text)

    # 1. Redact known secrets passed by callers
    if secrets:
        for secret in secrets:
            if secret and len(secret) >= 4:
                sanitized = sanitized.replace(secret, "[REDACTED]")

    # 2. Redact common API key patterns (OpenAI, Anthropic, Groq, IBM, Bearer)
    patterns = [
        r"sk-ant-[A-Za-z0-9_\-]{6,}",
        r"sk-[A-Za-z0-9_\-]{20,}",
        r"gsk_[A-Za-z0-9_\-]{20,}",
        r"Bearer\s+[A-Za-z0-9_\-\.]+",
        r"apikey\s*=\s*[A-Za-z0-9_\-]+",
        r"x-api-key\s*:\s*[A-Za-z0-9_\-]+",
        r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{8,}[\"']?",
    ]
    for pattern in patterns:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

    return sanitized


@dataclass
class ProviderError:
    """Structured, non-sensitive provider error information."""

    provider: str
    category: str  # authentication_error, quota_error, rate_limit_error, invalid_request_error, server_error, network_connection_error, unknown_error
    message: str
    status_code: int | None = None
    retryable: bool = False
    fallback_appropriate: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "category": self.category,
            "message": self.message,
            "status_code": self.status_code,
            "retryable": self.retryable,
            "fallback_appropriate": self.fallback_appropriate,
        }


def classify_http_error(
    provider: str,
    exc: error.HTTPError,
    secrets: list[str] | None = None,
) -> ProviderError:
    """Classify an HTTP error into an actionable, sanitized category."""
    code = exc.code
    err_body = ""
    try:
        err_body = exc.read().decode("utf-8", errors="ignore")
    except Exception:
        pass

    raw_message = f"HTTP {code}"
    try:
        data = json.loads(err_body)
        if isinstance(data, dict):
            if "error" in data:
                err_val = data["error"]
                if isinstance(err_val, dict) and "message" in err_val:
                    raw_message = err_val["message"]
                elif isinstance(err_val, str):
                    raw_message = err_val
            elif "message" in data:
                raw_message = data["message"]
            elif "errors" in data and isinstance(data["errors"], list) and data["errors"]:
                raw_message = data["errors"][0].get("message", raw_message)
    except Exception:
        if err_body:
            raw_message = err_body[:200]

    safe_message = sanitize_secret(raw_message, secrets)
    lowered = safe_message.lower()

    if code == 401 or any(
        w in lowered for w in ["unauthorized", "invalid api key", "invalid_api_key", "authentication", "forbidden"]
    ):
        category = "authentication_error"
        clean_msg = f"{provider.capitalize()} authentication failed: Invalid or expired API credentials."
        fallback_ok = True
        retryable = False

    elif code == 402 or any(
        w in lowered for w in ["credit balance", "insufficient quota", "insufficient_quota", "billing", "quota exceeded"]
    ):
        category = "quota_error"
        clean_msg = f"{provider.capitalize()} quota error: Credit balance is too low or quota is exhausted."
        fallback_ok = True
        retryable = False

    elif code == 429 or "rate limit" in lowered or "too many requests" in lowered:
        category = "rate_limit_error"
        clean_msg = f"{provider.capitalize()} rate limit exceeded: Too many requests. Please retry shortly."
        fallback_ok = True
        retryable = True

    elif code == 400:
        if any(w in lowered for w in ["credit", "balance", "quota", "billing", "plan", "credits"]):
            category = "quota_error"
            clean_msg = f"{provider.capitalize()} quota error: Credit balance is too low (Error 400)."
            fallback_ok = True
            retryable = False
        else:
            category = "invalid_request_error"
            clean_msg = f"{provider.capitalize()} invalid request (400): {safe_message[:150]}"
            fallback_ok = True
            retryable = False

    elif code in (500, 502, 503, 504) or any(
        w in lowered for w in ["bad gateway", "service unavailable", "gateway timeout", "internal server error"]
    ):
        category = "server_error"
        clean_msg = f"{provider.capitalize()} server error ({code}): Upstream model provider temporarily unavailable."
        fallback_ok = True
        retryable = True

    else:
        category = "invalid_request_error" if code < 500 else "server_error"
        clean_msg = f"{provider.capitalize()} error ({code}): {safe_message[:150]}"
        fallback_ok = True
        retryable = False

    return ProviderError(
        provider=provider,
        category=category,
        message=clean_msg,
        status_code=code,
        retryable=retryable,
        fallback_appropriate=fallback_ok,
    )


def classify_network_error(
    provider: str,
    exc: Exception,
    secrets: list[str] | None = None,
) -> ProviderError:
    """Classify connection / network exceptions."""
    safe_exc = sanitize_secret(str(exc), secrets)
    lowered = safe_exc.lower()

    if any(w in lowered for w in ["timeout", "timed out"]):
        category = "network_connection_error"
        clean_msg = f"{provider.capitalize()} request timed out."
        retryable = True
    elif any(
        w in lowered
        for w in [
            "connection refused",
            "name or service not known",
            "getaddrinfo failed",
            "nodename nor servname",
            "network is unreachable",
        ]
    ):
        category = "network_connection_error"
        clean_msg = f"{provider.capitalize()} connection failed: Unable to reach provider endpoint."
        retryable = True
    else:
        category = "unknown_error"
        clean_msg = f"{provider.capitalize()} exception: {safe_exc[:150]}"
        retryable = False

    return ProviderError(
        provider=provider,
        category=category,
        message=clean_msg,
        status_code=None,
        retryable=retryable,
        fallback_appropriate=True,
    )


# ==============================================================================
# 2. STRUCTURED GENERATION RESULTS (WITH TUPLE UNPACKING FOR BACKWARD COMPATIBILITY)
# ==============================================================================

@dataclass
class GenerationResult:
    """Structured result returned by UniversalModelClient.generate()."""

    text: str | None
    provider: str
    status: str  # "success", "fallback_success", "provider_error", "offline"
    source: str
    error: ProviderError | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def __iter__(self):
        """Allows unpacking as (text, provider) for complete backward compatibility."""
        yield self.text
        yield self.provider

    def __getitem__(self, index: int):
        return (self.text, self.provider)[index]


@dataclass
class JsonGenerationResult:
    """Structured result returned by UniversalModelClient.generate_json()."""

    data: dict[str, Any] | None
    provider: str
    status: str  # "success", "fallback_success", "provider_error", "offline"
    source: str
    error: ProviderError | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)

    def __iter__(self):
        """Allows unpacking as (data, provider) for complete backward compatibility."""
        yield self.data
        yield self.provider

    def __getitem__(self, index: int):
        return (self.data, self.provider)[index]


# ==============================================================================
# 3. TEXT & JSON EXTRACTION HELPERS
# ==============================================================================

def _extract_fenced_block(text: str, tag: str = "") -> str:
    """Safely extract content inside markdown code fences."""
    pattern = rf"```{tag}?\s*\n?(.*?)```" if tag else r"```(?:json|python|py)?\s*\n?(.*?)```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_code(text: str) -> str:
    """Extract Python source code from text, stripping fences if present."""
    if not text:
        return ""
    code = _extract_fenced_block(text, tag="python")
    if code == text.strip():
        code = _extract_fenced_block(text)
    return code.strip()


def extract_json(text: str) -> dict[str, Any] | None:
    """Safely extract and parse a JSON dictionary from model output."""
    if not text:
        return None

    cleaned = _extract_fenced_block(text, tag="json")
    if cleaned == text.strip():
        cleaned = _extract_fenced_block(text)

    # First attempt: direct parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Second attempt: locate outermost balanced { ... }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        substring = text[first_brace : last_brace + 1]
        try:
            data = json.loads(substring)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

def parse_image_data(img_str: str) -> tuple[str, str]:
    """Parse image data URL or raw base64 into (mime_type, base64_data)."""
    if not img_str:
        return "image/png", ""
    if img_str.startswith("data:") and ";base64," in img_str:
        prefix, b64_data = img_str.split(";base64,", 1)
        mime_type = prefix.replace("data:", "").strip() or "image/png"
        return mime_type, b64_data.strip()
    return "image/png", img_str.strip()


# ==============================================================================
# 4. PROVIDER ADAPTERS
# ==============================================================================

class BaseLLMProvider:
    """Abstract base class for LLM providers."""

    name: str = "base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def generate_with_error(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> tuple[str | None, ProviderError | None]:
        raise NotImplementedError

    def generate(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> str | None:
        text, _ = self.generate_with_error(prompt, system, temperature, images=images)
        return text

    def get_info(self) -> dict[str, Any]:
        raise NotImplementedError


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API client."""

    name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip()
        self.last_error: str | None = None
        self.last_error_detail: ProviderError | None = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_with_error(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> tuple[str | None, ProviderError | None]:
        if not self.is_available():
            err = ProviderError(
                provider=self.name,
                category="authentication_error",
                message="Anthropic API key is not configured.",
                status_code=None,
                retryable=False,
                fallback_appropriate=True,
            )
            self.last_error = err.message
            self.last_error_detail = err
            return None, err

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if images:
            for img in images:
                if not img or not isinstance(img, str):
                    continue
                mime_type, b64_data = parse_image_data(img)
                if b64_data:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": b64_data,
                        },
                    })

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            payload["system"] = system

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        self.last_error = None
                        self.last_error_detail = None
                        return block.get("text", ""), None
                return None, None
        except error.HTTPError as exc:
            prov_err = classify_http_error(self.name, exc, secrets=[self.api_key])
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[Anthropic Error {exc.code}]: {prov_err.message}", file=sys.stderr)
            return None, prov_err
        except Exception as exc:
            prov_err = classify_network_error(self.name, exc, secrets=[self.api_key])
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[Anthropic Exception]: {prov_err.message}", file=sys.stderr)
            return None, prov_err

    def get_info(self) -> dict[str, Any]:
        return {
            "provider": "anthropic",
            "model": self.model,
            "available": self.is_available(),
            "last_error": self.last_error,
            "last_error_category": self.last_error_detail.category if self.last_error_detail else None,
        }


class IBMWatsonxProvider(BaseLLMProvider):
    """IBM watsonx.ai provider supporting IBM Granite models."""

    name = "ibm-watsonx"

    def __init__(self) -> None:
        self.api_key = os.getenv("IBM_WATSONX_API_KEY", "").strip()
        self.project_id = os.getenv("IBM_WATSONX_PROJECT_ID", "").strip()
        self.base_url = (
            os.getenv("IBM_WATSONX_URL", "https://us-south.ml.cloud.ibm.com").strip().rstrip("/")
        )
        self.model_id = os.getenv("IBM_WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct").strip()
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self.last_error: str | None = None
        self.last_error_detail: ProviderError | None = None

    def is_available(self) -> bool:
        return bool(self.api_key and self.project_id)

    def _get_iam_token(self) -> tuple[str | None, ProviderError | None]:
        now = time.time()
        if self._token and now < self._token_expiry:
            return self._token, None

        data = parse.urlencode(
            {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self.api_key}
        ).encode("utf-8")

        req = request.Request(
            "https://iam.cloud.ibm.com/identity/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                self._token = body.get("access_token")
                self._token_expiry = now + 3000
                return self._token, None
        except error.HTTPError as exc:
            prov_err = classify_http_error(self.name, exc, secrets=[self.api_key])
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[IBM IAM Auth Error]: {prov_err.message}", file=sys.stderr)
            return None, prov_err
        except Exception as exc:
            prov_err = classify_network_error(self.name, exc, secrets=[self.api_key])
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[IBM IAM Auth Error]: {prov_err.message}", file=sys.stderr)
            return None, prov_err

    def generate_with_error(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> tuple[str | None, ProviderError | None]:
        if not self.is_available():
            err = ProviderError(
                provider=self.name,
                category="authentication_error",
                message="IBM watsonx credentials (API key or Project ID) are not configured.",
                status_code=None,
                retryable=False,
                fallback_appropriate=True,
            )
            self.last_error = err.message
            self.last_error_detail = err
            return None, err

        token, auth_err = self._get_iam_token()
        if not token:
            return None, auth_err

        endpoint = f"{self.base_url}/ml/v1/text/generation?version=2023-05-29"
        effective_prompt = prompt
        if images:
            effective_prompt += f"\n\n[Note: User attached {len(images)} image(s)/screenshot(s). Analyze code/problem context accordingly.]"
        input_text = f"<|system|>\n{system}\n<|user|>\n{effective_prompt}\n<|assistant|>\n" if system else effective_prompt

        payload = {
            "input": input_text,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 3000,
                "temperature": temperature,
            },
            "model_id": self.model_id,
            "project_id": self.project_id,
        }

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )

        secrets = [self.api_key, token]
        try:
            with request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                results = body.get("results", [])
                if results:
                    self.last_error = None
                    self.last_error_detail = None
                    return results[0].get("generated_text", ""), None
                return None, None
        except error.HTTPError as exc:
            prov_err = classify_http_error(self.name, exc, secrets=secrets)
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[IBM watsonx Error]: {prov_err.message}", file=sys.stderr)
            return None, prov_err
        except Exception as exc:
            prov_err = classify_network_error(self.name, exc, secrets=secrets)
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[IBM watsonx Error]: {prov_err.message}", file=sys.stderr)
            return None, prov_err

    def get_info(self) -> dict[str, Any]:
        return {
            "provider": "ibm-watsonx",
            "model": self.model_id,
            "project_id": (self.project_id[:6] + "...") if self.project_id else "",
            "available": self.is_available(),
            "last_error": self.last_error,
            "last_error_category": self.last_error_detail.category if self.last_error_detail else None,
        }


class OpenAICompatibleProvider(BaseLLMProvider):
    """Generic OpenAI-compatible provider (OpenAI, Groq, OpenRouter, Ollama)."""

    def __init__(
        self,
        name: str,
        api_key_env: str,
        default_model: str,
        default_url: str,
        model_env: str,
        url_env: str,
        requires_key: bool = True,
    ) -> None:
        self.name = name
        self.requires_key = requires_key
        self.api_key = os.getenv(api_key_env, "").strip() if api_key_env else ""
        self.model = os.getenv(model_env, default_model).strip()
        self.base_url = os.getenv(url_env, default_url).strip()
        self.last_error: str | None = None
        self.last_error_detail: ProviderError | None = None

    def is_available(self) -> bool:
        if self.requires_key:
            return bool(self.api_key)
        return bool(self.base_url)

    def generate_with_error(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> tuple[str | None, ProviderError | None]:
        if self.requires_key and not self.api_key:
            err = ProviderError(
                provider=self.name,
                category="authentication_error",
                message=f"{self.name.capitalize()} API key is not configured.",
                status_code=None,
                retryable=False,
                fallback_appropriate=True,
            )
            self.last_error = err.message
            self.last_error_detail = err
            return None, err

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if images:
            for img in images:
                if not img or not isinstance(img, str):
                    continue
                mime_type, b64_data = parse_image_data(img)
                if b64_data:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
                    })

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content if images else prompt})

        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": messages,
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(self.base_url, data=data, headers=headers, method="POST")

        secrets = [self.api_key] if self.api_key else []
        try:
            with request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    self.last_error = None
                    self.last_error_detail = None
                    return choices[0].get("message", {}).get("content", ""), None
                return None, None
        except error.HTTPError as exc:
            prov_err = classify_http_error(self.name, exc, secrets=secrets)
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[{self.name} Error]: {prov_err.message}", file=sys.stderr)
            return None, prov_err
        except Exception as exc:
            prov_err = classify_network_error(self.name, exc, secrets=secrets)
            self.last_error = prov_err.message
            self.last_error_detail = prov_err
            print(f"[{self.name} Error]: {prov_err.message}", file=sys.stderr)
            return None, prov_err

    def get_info(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "model": self.model,
            "available": self.is_available(),
            "last_error": self.last_error,
            "last_error_category": self.last_error_detail.category if self.last_error_detail else None,
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini model provider using Google AI Studio REST API."""

    def __init__(self) -> None:
        self.name = "gemini"
        self.api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip()
        self.last_error: str | None = None
        self.last_error_detail: ProviderError | None = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_with_error(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> tuple[str | None, ProviderError | None]:
        if not self.api_key:
            err = ProviderError(
                provider="gemini",
                category="authentication_error",
                message="Google Gemini API key is not configured.",
                status_code=None,
                retryable=False,
                fallback_appropriate=True,
            )
            self.last_error = err.message
            self.last_error_detail = err
            return None, err

        candidate_models = [self.model]
        for fallback in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-flash-latest"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        last_prov_err: ProviderError | None = None
        secrets = [self.api_key]

        parts: list[dict[str, Any]] = [{"text": prompt}]
        if images:
            for img in images:
                if not img or not isinstance(img, str):
                    continue
                mime_type, b64_data = parse_image_data(img)
                if b64_data:
                    parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data,
                        }
                    })

        for mod in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={self.api_key}"
            payload: dict[str, Any] = {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "temperature": temperature,
                },
            }
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}

            if "json" in prompt.lower() or "json" in system.lower():
                payload["generationConfig"]["responseMimeType"] = "application/json"

            data = json.dumps(payload).encode("utf-8")
            req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

            try:
                with request.urlopen(req, timeout=35) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    candidates = body.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            self.last_error = None
                            self.last_error_detail = None
                            return parts[0].get("text", ""), None
                    return None, None
            except error.HTTPError as exc:
                prov_err = classify_http_error(self.name, exc, secrets=secrets)
                last_prov_err = prov_err
                if exc.code in (404, 503):
                    continue
                self.last_error = prov_err.message
                self.last_error_detail = prov_err
                print(f"[Gemini Error]: {prov_err.message}", file=sys.stderr)
                return None, prov_err
            except Exception as exc:
                prov_err = classify_network_error(self.name, exc, secrets=secrets)
                last_prov_err = prov_err
                self.last_error = prov_err.message
                self.last_error_detail = prov_err
                print(f"[Gemini Error]: {prov_err.message}", file=sys.stderr)
                return None, prov_err

        if last_prov_err:
            self.last_error = last_prov_err.message
            self.last_error_detail = last_prov_err
            return None, last_prov_err

        return None, None

    def get_info(self) -> dict[str, Any]:
        return {
            "provider": "gemini",
            "model": self.model,
            "available": self.is_available(),
            "last_error": self.last_error,
            "last_error_category": self.last_error_detail.category if self.last_error_detail else None,
        }


# ==============================================================================
# 5. UNIVERSAL MODEL CLIENT (CHAIN ORCHESTRATION & STRUCTURED REPORTING)
# ==============================================================================

class UniversalModelClient:
    """Orchestrates multi-provider resolution with graceful failover and error tracking."""

    def __init__(self) -> None:
        self.gemini = GeminiProvider()
        self.anthropic = AnthropicProvider()
        self.ibm_watsonx = IBMWatsonxProvider()
        self.openai = OpenAICompatibleProvider(
            name="openai",
            api_key_env="OPENAI_API_KEY",
            default_model="gpt-4o-mini",
            default_url="https://api.openai.com/v1/chat/completions",
            model_env="OPENAI_MODEL",
            url_env="OPENAI_BASE_URL",
        )
        self.groq = OpenAICompatibleProvider(
            name="groq",
            api_key_env="GROQ_API_KEY",
            default_model="llama-3.3-70b-versatile",
            default_url="https://api.groq.com/openai/v1/chat/completions",
            model_env="GROQ_MODEL",
            url_env="GROQ_BASE_URL",
        )
        self.openrouter = OpenAICompatibleProvider(
            name="openrouter",
            api_key_env="OPENROUTER_API_KEY",
            default_model="meta-llama/llama-3.3-70b-instruct",
            default_url="https://openrouter.ai/api/v1/chat/completions",
            model_env="OPENROUTER_MODEL",
            url_env="OPENROUTER_BASE_URL",
        )
        self.ollama = OpenAICompatibleProvider(
            name="ollama",
            api_key_env="",
            default_model="qwen2.5-coder:latest",
            default_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1/chat/completions"),
            model_env="OLLAMA_MODEL",
            url_env="OLLAMA_BASE_URL",
            requires_key=False,
        )
        self.last_result: GenerationResult | None = None
        self.last_error: str | None = None

    def _get_provider_chain(self) -> list[BaseLLMProvider]:
        """Resolve ordered provider chain honoring MODEL_PROVIDER if set."""
        explicit = os.getenv("MODEL_PROVIDER", "").strip().lower()
        if explicit in {"gemini", "google"}:
            return [self.gemini]
        if explicit in {"anthropic", "claude"}:
            return [self.anthropic]
        if explicit in {"ibm", "watsonx", "ibm-watsonx", "granite"}:
            return [self.ibm_watsonx]
        if explicit in {"openai"}:
            return [self.openai]
        if explicit in {"groq"}:
            return [self.groq]
        if explicit in {"openrouter"}:
            return [self.openrouter]
        if explicit in {"ollama"}:
            return [self.ollama]
        if explicit in {"local", "offline"}:
            return []

        # Standard Priority Order:
        # 1. Gemini (if configured)
        # 2. Anthropic
        # 3. IBM watsonx.ai
        # 4. OpenAI
        # 5. Groq
        # 6. OpenRouter
        # 7. Ollama (if configured in env)
        chain: list[BaseLLMProvider] = []
        if self.gemini.is_available():
            chain.append(self.gemini)
        if self.anthropic.is_available():
            chain.append(self.anthropic)
        if self.ibm_watsonx.is_available():
            chain.append(self.ibm_watsonx)
        if self.openai.is_available():
            chain.append(self.openai)
        if self.groq.is_available():
            chain.append(self.groq)
        if self.openrouter.is_available():
            chain.append(self.openrouter)
        if os.getenv("OLLAMA_BASE_URL"):
            chain.append(self.ollama)

        return chain

    def generate(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> GenerationResult:
        """Try available providers in priority order, returning a structured GenerationResult."""
        chain = self._get_provider_chain()
        attempts: list[dict[str, Any]] = []

        if not chain:
            res = GenerationResult(
                text=None,
                provider="offline",
                status="offline",
                source="offline",
                error=None,
                attempts=[],
            )
            self.last_result = res
            self.last_error = None
            return res

        first_error: ProviderError | None = None
        for i, provider in enumerate(chain):
            try:
                try:
                    res_text, prov_err = provider.generate_with_error(
                        prompt, system=system, temperature=temperature, images=images
                    )
                except TypeError as type_err:
                    if "images" in str(type_err):
                        res_text, prov_err = provider.generate_with_error(
                            prompt, system=system, temperature=temperature
                        )
                    else:
                        raise
                if prov_err:
                    attempts.append({
                        "provider": provider.name,
                        "success": False,
                        "category": prov_err.category,
                        "message": prov_err.message,
                        "status_code": prov_err.status_code,
                    })
                    if first_error is None:
                        first_error = prov_err

                if res_text and res_text.strip():
                    status = "success" if i == 0 else "fallback_success"
                    attempts.append({
                        "provider": provider.name,
                        "success": True,
                        "category": None,
                        "message": "OK",
                    })
                    res = GenerationResult(
                        text=res_text.strip(),
                        provider=provider.name,
                        status=status,
                        source=provider.name,
                        error=None,
                        attempts=attempts,
                    )
                    self.last_result = res
                    self.last_error = None
                    return res

                if prov_err and not prov_err.fallback_appropriate:
                    break
            except Exception as exc:
                cat_err = classify_network_error(provider.name, exc)
                attempts.append({
                    "provider": provider.name,
                    "success": False,
                    "category": cat_err.category,
                    "message": cat_err.message,
                })
                if first_error is None:
                    first_error = cat_err
                print(f"[Provider {provider.name} failed]: {cat_err.message}", file=sys.stderr)
                continue

        # All configured providers in chain failed
        primary_name = chain[0].name
        primary_err = first_error or ProviderError(
            provider=primary_name,
            category="unknown_error",
            message=f"All configured model providers ({', '.join(p.name for p in chain)}) failed.",
            status_code=None,
            retryable=False,
            fallback_appropriate=False,
        )
        res = GenerationResult(
            text=None,
            provider=primary_name,
            status="provider_error",
            source=primary_name,
            error=primary_err,
            attempts=attempts,
        )
        self.last_result = res
        self.last_error = primary_err.message
        return res

    def generate_json(
        self, prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None
    ) -> JsonGenerationResult:
        """Generate structured JSON response with automatic cleanup, failover, and status tracking."""
        json_system = (
            (system + "\n\n" if system else "")
            + "IMPORTANT: You must return ONLY valid raw JSON with no markdown formatting, no code fences, and no preamble."
        )
        gen_res = self.generate(prompt, system=json_system, temperature=temperature, images=images)
        if gen_res.status == "provider_error":
            return JsonGenerationResult(
                data=None,
                provider=gen_res.provider,
                status="provider_error",
                source=gen_res.source,
                error=gen_res.error,
                attempts=gen_res.attempts,
            )
        if not gen_res.text:
            return JsonGenerationResult(
                data=None,
                provider=gen_res.provider,
                status=gen_res.status,
                source=gen_res.source,
                error=gen_res.error,
                attempts=gen_res.attempts,
            )

        data = extract_json(gen_res.text)
        if data is None and gen_res.status in ("success", "fallback_success"):
            parse_err = ProviderError(
                provider=gen_res.provider,
                category="invalid_request_error",
                message=f"{gen_res.provider.capitalize()} returned output that could not be parsed as valid JSON.",
                status_code=None,
                retryable=False,
                fallback_appropriate=True,
            )
            return JsonGenerationResult(
                data=None,
                provider=gen_res.provider,
                status="provider_error",
                source=gen_res.source,
                error=parse_err,
                attempts=gen_res.attempts,
            )

        return JsonGenerationResult(
            data=data,
            provider=gen_res.provider,
            status=gen_res.status,
            source=gen_res.source,
            error=gen_res.error,
            attempts=gen_res.attempts,
        )

    def get_active_provider_info(self) -> dict[str, Any]:
        """Return non-sensitive telemetry about active and configured providers."""
        chain = self._get_provider_chain()
        active = chain[0].get_info() if chain else {"provider": "offline", "model": "local-fallback"}
        configured = [p.name for p in chain]
        last_res = getattr(self, "last_result", None)
        return {
            "active": active,
            "configured_providers": configured,
            "mode": active.get("provider", "offline"),
            "generation_status": last_res.status if last_res else ("offline" if not chain else "ready"),
            "generation_source": last_res.source if last_res else ("offline" if not chain else active.get("provider", "offline")),
            "last_error": self.last_error or (last_res.error.message if (last_res and last_res.error) else active.get("last_error")),
            "last_error_category": last_res.error.category if (last_res and last_res.error) else None,
            "attempts": [a for a in (last_res.attempts if last_res else [])],
        }


# Global singleton instance
CLIENT = UniversalModelClient()


def generate(prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None) -> GenerationResult:
    return CLIENT.generate(prompt, system, temperature, images=images)


def generate_json(prompt: str, system: str = "", temperature: float = 0.1, images: list[str] | None = None) -> JsonGenerationResult:
    return CLIENT.generate_json(prompt, system, temperature, images=images)


def complete(system: str, user: str) -> str | None:
    """Backward-compatible helper."""
    text, _ = CLIENT.generate(prompt=user, system=system)
    return text


def complete_json(system: str, user: str) -> dict[str, Any] | None:
    """Backward-compatible helper."""
    data, _ = CLIENT.generate_json(prompt=user, system=system)
    return data


def get_active_provider_info() -> dict[str, Any]:
    return CLIENT.get_active_provider_info()