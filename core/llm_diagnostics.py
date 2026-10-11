import json
import os
from urllib.parse import urlsplit, urlunsplit

import requests

from .config import (
    LLM_PROVIDER,
    OMNIROUTE_BASE_URL,
    OLLAMA_URL,
)


def _safe_url(value):
    """Remove URL credentials and query parameters before reporting a URL."""
    try:
        parsed = urlsplit(str(value))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return "<invalid-url>"

        hostname = parsed.hostname
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"

        port = parsed.port
        netloc = hostname + (f":{port}" if port is not None else "")
        path = parsed.path.rstrip("/")
        return urlunsplit((parsed.scheme, netloc, path, "", ""))
    except (TypeError, ValueError):
        return "<invalid-url>"


def _valid_url(value):
    try:
        parsed = urlsplit(str(value))
        return (
            parsed.scheme in ("http", "https")
            and parsed.hostname is not None
            and parsed.port != 0
        )
    except (TypeError, ValueError):
        return False


def _result(provider, url, status, reachable, detail, **extra):
    return {
        "provider": provider,
        "status": status,
        "reachable": reachable,
        "url": _safe_url(url),
        "detail": detail,
        **extra,
    }


def _transport_failure(provider, url, exc, **extra):
    if isinstance(exc, requests.Timeout):
        status = "timeout"
        detail = "The request timed out."
    elif isinstance(exc, requests.ConnectionError):
        status = "unreachable"
        detail = "Cannot connect. Check that the service is running and the URL is correct."
    else:
        status = "request_error"
        detail = "The request failed. Check the service configuration and logs."

    return _result(
        provider, url, status, False, detail, **extra
    )


def _http_failure(provider, url, status_code, api_key_configured=False):
    extra = {"http_status": status_code}
    if provider == "omniroute":
        extra["api_key_configured"] = api_key_configured

    if status_code in (401, 403):
        if provider == "omniroute" and not api_key_configured:
            return _result(
                provider, url, "authentication_required", True,
                "The endpoint is reachable but requires credentials.",
                **extra,
            )
        return _result(
            provider, url, "authentication_rejected", True,
            "The endpoint is reachable but rejected the credentials or permissions.",
            **extra,
        )

    if status_code == 404:
        status = "endpoint_not_found"
        detail = "The service responded, but this endpoint was not found."
    elif status_code >= 500:
        status = "server_error"
        detail = "The service returned a server-side error."
    else:
        status = "http_error"
        detail = "The service returned an unsuccessful HTTP status."

    return _result(
        provider, url, status, True, detail, **extra
    )


def _extract_names(payload, collection_key, name_key):
    if not isinstance(payload, dict):
        return None

    items = payload.get(collection_key)
    if not isinstance(items, list):
        return None

    names = sorted({
        item[name_key]
        for item in items
        if isinstance(item, dict)
        and isinstance(item.get(name_key), str)
        and item[name_key].strip()
    })
    return names


def probe_omniroute(base_url=None, api_key=None, timeout=4):
    """Probe the configured OpenAI-compatible model catalog without running a model."""
    base_url = (
        OMNIROUTE_BASE_URL if base_url is None else str(base_url)
    ).rstrip("/")
    api_key = (
        os.getenv("OMNIROUTE_API_KEY", "").strip()
        if api_key is None else str(api_key).strip()
    )

    common = {"api_key_configured": bool(api_key)}
    if not _valid_url(base_url):
        return _result(
            "omniroute", base_url, "invalid_configuration", False,
            "Configure a valid HTTP(S) gateway base URL.",
            **common,
        )

    url = f"{base_url}/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        return _transport_failure("omniroute", url, exc, **common)
    except requests.ConnectionError as exc:
        return _transport_failure("omniroute", url, exc, **common)
    except requests.RequestException as exc:
        return _transport_failure("omniroute", url, exc, **common)

    status_code = response.status_code
    if not 200 <= status_code < 300:
        return _http_failure(
            "omniroute", url, status_code, bool(api_key)
        )

    try:
        payload = response.json()
    except ValueError:
        return _result(
            "omniroute", url, "invalid_response", True,
            "The model catalog returned invalid JSON.",
            http_status=status_code, **common,
        )

    models = _extract_names(payload, "data", "id")
    if models is None:
        return _result(
            "omniroute", url, "invalid_response", True,
            "The response did not contain the expected model catalog.",
            http_status=status_code, **common,
        )

    return _result(
        "omniroute", url, "ready", True,
        "The model catalog responded successfully.",
        http_status=status_code,
        model_count=len(models),
        models=models[:12],
        **common,
    )


def probe_ollama(base_url=None, timeout=4):
    """Probe Ollama's local model catalog without generating a response."""
    base_url = (OLLAMA_URL if base_url is None else str(base_url)).rstrip("/")

    if not _valid_url(base_url):
        return _result(
            "ollama", base_url, "invalid_configuration", False,
            "Configure a valid HTTP(S) Ollama base URL.",
        )

    if base_url.endswith("/api/tags"):
        url = base_url
    elif base_url.endswith("/api"):
        url = f"{base_url}/tags"
    else:
        url = f"{base_url}/api/tags"

    try:
        response = requests.get(url, timeout=timeout)
    except requests.Timeout as exc:
        return _transport_failure("ollama", url, exc)
    except requests.ConnectionError as exc:
        return _transport_failure("ollama", url, exc)
    except requests.RequestException as exc:
        return _transport_failure("ollama", url, exc)

    status_code = response.status_code
    if not 200 <= status_code < 300:
        return _http_failure("ollama", url, status_code)

    try:
        payload = response.json()
    except ValueError:
        return _result(
            "ollama", url, "invalid_response", True,
            "The model catalog returned invalid JSON.",
            http_status=status_code,
        )

    models = _extract_names(payload, "models", "name")
    if models is None:
        return _result(
            "ollama", url, "invalid_response", True,
            "The response did not contain the expected model catalog.",
            http_status=status_code,
        )

    return _result(
        "ollama", url, "ready", True,
        "The local model catalog responded successfully.",
        http_status=status_code,
        model_count=len(models),
        models=models[:12],
    )


def diagnose_providers(timeout=4):
    """Return a secret-safe snapshot of configured model-provider readiness."""
    return {
        "active_provider": LLM_PROVIDER,
        "omniroute": probe_omniroute(timeout=timeout),
        "ollama": probe_ollama(timeout=timeout),
    }


def main():
    print(json.dumps(diagnose_providers(), indent=2))


if __name__ == "__main__":
    main()
