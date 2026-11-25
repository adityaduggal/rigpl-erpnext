"""
One HTTP session for the carrier APIs (#168, #152): a timeout on each call, the TLS check
on, and retries on 429 and 5xx. Tokens are cached in Redis until they expire.
"""
import json
from typing import Callable, Optional, Tuple

import frappe
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import ProviderError

TIMEOUT = (10, 45)  # (connect, read) seconds
_session = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        retry = Retry(total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset(("GET", "POST", "PUT", "DELETE")), raise_on_status=False)
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry))
        _session = session
    return _session


def redact(value, limit: int = 120):
    """The same data with each long text cut, so a PDF in base64 does not fill the screen."""
    if isinstance(value, dict):
        return {k: redact(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, limit) for v in value]
    if isinstance(value, str) and len(value) > limit:
        return f"<{len(value)} characters>"
    return value


def step(name: str, method: str, url: str, body=None) -> dict:
    """One call of a preview (nothing is sent). No query string and no header, long text cut."""
    return {"step": name, "method": method, "url": url.split("?")[0], "body": redact(body)}


def blocked_message(method: str, url: str, provider: str, body) -> str:
    """The text for a call that site_config `shipping_block_calls` stopped. No query string,
    and no form data (the login holds the secret key)."""
    text = f"{provider}: calls are blocked on this site (shipping_block_calls). Not sent: {method} {url.split('?')[0]}"
    return text + ("\n" + json.dumps(redact(body), indent=1, default=str) if body else "")


def request(method: str, url: str, provider: str, **kwargs) -> requests.Response:
    """A request with the default timeout. A network error becomes ProviderError, with the
    URL path only, never the query string (it can hold a password)."""
    if frappe.conf.get("shipping_block_calls"):
        raise ProviderError(blocked_message(method, url, provider, kwargs.get("json")))
    kwargs.setdefault("timeout", TIMEOUT)
    kwargs.setdefault("verify", True)
    try:
        return get_session().request(method, url, **kwargs)
    except requests.RequestException as e:
        raise ProviderError(f"{provider}: {method} {url.split('?')[0]} failed: {type(e).__name__}") from None


def json_or_error(response: requests.Response, provider: str) -> dict:
    try:
        return response.json()
    except ValueError:
        raise ProviderError(
            f"{provider}: {response.request.method} {response.url.split('?')[0]} gave HTTP "
            f"{response.status_code}, not JSON: {response.text[:200]}"
        ) from None


def cached_token(key: str, fetch: Callable[[], Tuple[str, int]]) -> str:
    """The token in Redis for `key`, or a new one from `fetch()` -> (token, seconds valid).
    It is kept 60 seconds less than its life, so it never expires during a call."""
    cache_key = f"rigpl_shipping_token:{key}"
    # expires=True: without it v13 keeps the first miss (None) in frappe.local.cache, and
    # every later call in the same job logs in again
    token: Optional[str] = frappe.cache().get_value(cache_key, expires=True)
    if token:
        return token
    token, seconds = fetch()
    frappe.cache().set_value(cache_key, token, expires_in_sec=max(60, int(seconds) - 60))
    return token


def clear_token(key: str) -> None:
    frappe.cache().delete_value(f"rigpl_shipping_token:{key}")
