"""
One HTTP session for the carrier APIs (#168, #152): a timeout on each call, the TLS check
on, and retries on 429 and 5xx. Tokens are cached in Redis until they expire.
"""
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


def request(method: str, url: str, provider: str, **kwargs) -> requests.Response:
    """A request with the default timeout. A network error becomes ProviderError, with the
    URL path only, never the query string (it can hold a password)."""
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
    token: Optional[str] = frappe.cache().get_value(cache_key)
    if token:
        return token
    token, seconds = fetch()
    frappe.cache().set_value(cache_key, token, expires_in_sec=max(60, int(seconds) - 60))
    return token


def clear_token(key: str) -> None:
    frappe.cache().delete_value(f"rigpl_shipping_token:{key}")
