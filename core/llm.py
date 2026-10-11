import os
import requests
from .config import (
    OLLAMA_URL, OLLAMA_MODEL,
    OMNIROUTE_BASE_URL, OMNIROUTE_MODEL, LLM_PROVIDER
)

_active_model = OMNIROUTE_MODEL


def _api_key():
    key = os.getenv("OMNIROUTE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OMNIROUTE_API_KEY is not set in this terminal.")
    return key


def _request_omniroute(operation, request):
    """Make an OmniRoute request with actionable, secret-safe errors."""
    try:
        response = request()
        response.raise_for_status()
        return response
    except requests.Timeout as exc:
        raise RuntimeError(
            f"OmniRoute {operation} timed out. Check gateway health "
            "and provider response time."
        ) from exc
    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"OmniRoute {operation} failed: cannot connect to "
            f"{OMNIROUTE_BASE_URL}. Check that the gateway is running "
            "and OMNIROUTE_BASE_URL is correct."
        ) from exc
    except requests.HTTPError as exc:
        status = getattr(
            getattr(exc, "response", None), "status_code", None
        )
        status_text = (
            f"HTTP {status}" if status is not None else "an HTTP error"
        )
        raise RuntimeError(
            f"OmniRoute {operation} failed with {status_text}. "
            "Check the API key, endpoint path, and gateway logs."
        ) from exc


def _error_summary(error):
    """Return concise diagnostic text without exposing response bodies."""
    if isinstance(error, RuntimeError):
        return str(error)
    if isinstance(error, requests.Timeout):
        return "request timed out"
    if isinstance(error, requests.ConnectionError):
        return "connection failed; the service may be stopped or unreachable"
    if isinstance(error, requests.HTTPError):
        status = getattr(
            getattr(error, "response", None), "status_code", None
        )
        return f"HTTP {status}" if status is not None else "HTTP error"
    return type(error).__name__


def list_omniroute_models():
    response = _request_omniroute(
        "model discovery",
        lambda: requests.get(
            f"{OMNIROUTE_BASE_URL}/models",
            headers={"Authorization": f"Bearer {_api_key()}"},
            timeout=30,
        ),
    )
    data = response.json()
    return sorted({
        item["id"] for item in data.get("data", [])
        if isinstance(item, dict) and item.get("id")
    })


def get_active_model():
    return _active_model


def set_active_model(model_id):
    global _active_model
    model_id = model_id.strip()
    if not model_id:
        return False
    if model_id not in set(list_omniroute_models()):
        return False
    _active_model = model_id
    return True


def _ask_omniroute(messages, model):
    response = _request_omniroute(
        "chat completion",
        lambda: requests.post(
            f"{OMNIROUTE_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "max_tokens": 2048,
            },
            timeout=120,
        ),
    )
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OmniRoute returned no completion choices.")

    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        answer = "\n".join(part for part in parts if part).strip()
        if answer:
            return answer
    raise RuntimeError("Selected model returned no text response.")


def _ask_ollama(messages, ollama_url=None, ollama_model=None):
    url = (ollama_url or OLLAMA_URL).rstrip("/")
    if not url.endswith("/api/chat"):
        url += "/api/chat"
    response = requests.post(
        url,
        json={
            "model": ollama_model or OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        },
        timeout=120
    )
    response.raise_for_status()
    answer = ((response.json().get("message") or {}).get("content") or "").strip()
    if not answer:
        raise RuntimeError("Ollama returned no text response.")
    return answer


def ask_messages(messages, ollama_url=None, ollama_model=None):
    if LLM_PROVIDER == "ollama":
        return _ask_ollama(messages, ollama_url, ollama_model)
    try:
        return _ask_omniroute(messages, get_active_model())
    except Exception as omni_error:
        try:
            return _ask_ollama(messages, ollama_url, ollama_model)
        except Exception as ollama_error:
            raise RuntimeError(
                "Both OmniRoute and Ollama failed. "
                f"OmniRoute: {_error_summary(omni_error)}; "
                f"Ollama: {_error_summary(ollama_error)}"
            ) from ollama_error


def ask_ollama(prompt, system=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return ask_messages(messages)
