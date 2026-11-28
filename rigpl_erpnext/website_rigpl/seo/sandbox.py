"""
Evaluates one Jinja source of a Schema Template. The environment is not Frappe's: it has no
`frappe` object and no loader, and it cannot change the lists and dicts that it gets.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional
from urllib.parse import quote

from frappe.utils import get_url, strip_html_tags
from jinja2 import StrictUndefined, Undefined, nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment


def evaluate(source: str, variables: dict) -> Any:
    """One `{{ x }}`, or bare `x`, gives the value of `x`. Any other source gives a string."""
    source = (source or "").strip()
    if not source:
        return None

    is_expression, compiled = compile_source(source)
    if not is_expression:
        return compiled.render(variables).strip()

    result = compiled(variables)
    if isinstance(result, Undefined):
        result._fail_with_undefined_error()
    # filters such as `map` return an iterator
    return list(result) if hasattr(result, "__next__") else result


def check_syntax(source: str) -> None:
    source = (source or "").strip()
    if source:
        compile_source(source)


@lru_cache(maxsize=1024)
def compile_source(source: str) -> tuple:
    expression = get_expression(source)
    if expression is None:
        return False, ENVIRONMENT.from_string(source)
    return True, ENVIRONMENT.compile_expression(expression, undefined_to_none=False)


def get_expression(source: str) -> Optional[str]:
    """The expression of a source that is only one expression, else None."""
    if "{{" not in source and "{%" not in source:
        return source

    body = ENVIRONMENT.parse(source).body
    if len(body) != 1 or not isinstance(body[0], nodes.Output):
        return None
    parts = body[0].nodes
    if len(parts) != 1 or isinstance(parts[0], nodes.TemplateData):
        return None
    if not (source.startswith("{{") and source.endswith("}}")):
        return None

    inner = source[2:-2]
    if inner.startswith("-"):
        inner = inner[1:]
    if inner.endswith("-"):
        inner = inner[:-1]
    return inner


def plain_text(value) -> str:
    return " ".join(strip_html_tags(str(value or "")).split())


def abs_url(value) -> str:
    """An absolute, URL-encoded address. An empty value stays empty."""
    url = str(value or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = get_url("/" + url.lstrip("/"))
    return quote(url, safe=":/?&=#%")


def make_environment() -> ImmutableSandboxedEnvironment:
    environment = ImmutableSandboxedEnvironment(undefined=StrictUndefined)
    environment.globals.clear()
    environment.filters.update(plain_text=plain_text, abs_url=abs_url)
    return environment


ENVIRONMENT = make_environment()
