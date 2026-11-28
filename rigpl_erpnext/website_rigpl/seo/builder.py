"""
Builds the schema.org `@graph` of a page from Schema Templates. An expression that fails
drops only its own property: the error goes to `errors`, and `log_errors` writes it.
"""
from __future__ import annotations

import json
from collections import namedtuple
from datetime import date
from decimal import Decimal
from typing import List, Optional

import frappe

from .sandbox import evaluate

DOCTYPE = "Schema Template"
BLOCK_TEMPLATES = "Web Template"
# like Site templates, every page outputs them
PAGE_PARTS = ("Breadcrumb", "Navigation")
NAMES_CACHE_KEY = "rigpl_schema_templates"
ERROR_CACHE_KEY = "rigpl_schema_error"
LOG_ONCE_SECONDS = 3600
SCRIPT_ESCAPES = (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"))

BuildError = namedtuple("BuildError", "template property message")


def get_template_names(applies_to: str) -> List[str]:
    def read_names():
        filters = {"enabled": 1, "applies_to": applies_to}
        return frappe.get_all(DOCTYPE, filters=filters, order_by="name", pluck="name")

    return frappe.cache().hget(NAMES_CACHE_KEY, applies_to, generator=read_names)


def clear_template_cache(path=None) -> None:
    """Also the `website_clear_cache` hook, which passes a path."""
    frappe.cache().delete_value(NAMES_CACHE_KEY)


def build_graph(
    templates: list, variables: dict, errors: List[BuildError], blocks: list = ()
) -> Optional[dict]:
    return make_graph(build_page_nodes(templates, variables, blocks, errors))


def build_nodes(templates: list, variables: dict, errors: List[BuildError]) -> List[dict]:
    return build_page_nodes(templates, variables, [], errors)


def build_page_nodes(
    templates: list, variables: dict, blocks: list, errors: List[BuildError]
) -> List[dict]:
    builder = GraphBuilder(errors)
    enabled = [t for t in templates if t.enabled]
    return merge_by_id([node for t in enabled for node in builder.page_nodes(t, variables, blocks)])


def make_graph(nodes: List[dict]) -> Optional[dict]:
    return {"@context": "https://schema.org", "@graph": nodes} if nodes else None


def to_script(graph: dict) -> str:
    text = to_json(graph)
    # a value must not close the script tag
    for character, escape in SCRIPT_ESCAPES:
        text = text.replace(character, escape)
    return '<script type="application/ld+json">{}</script>'.format(text)


def to_json(value, indent: int = None) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, default=json_default, indent=indent)


def log_errors(errors: List[BuildError], route: str) -> None:
    """One Error Log for each template, property and route in an hour: some pages are not cached."""
    for error in errors:
        key = "|".join((ERROR_CACHE_KEY, error.template, error.property, route))
        if frappe.cache().get_value(key, expires=True):
            continue
        title = "Schema error: {} {}".format(error.template, route)[:140]
        message = "Template: {}\nProperty: {}\nRoute: {}\n\n{}".format(
            error.template, error.property, route, error.message
        )
        frappe.log_error(message, title)
        frappe.cache().set_value(key, 1, expires_in_sec=LOG_ONCE_SECONDS)
        # a GET request does not commit without this flag
        frappe.local.flags.commit = True


class GraphBuilder:
    def __init__(self, errors: List[BuildError]):
        self.errors = errors
        # templates that passed `iterate_over` and `condition` at least one time
        self.reached = set()

    def page_nodes(self, template, variables: dict, blocks: list) -> List[dict]:
        """A Web Template template makes its nodes for each block of that Web Template."""
        if template.applies_to != BLOCK_TEMPLATES:
            return self.nodes(template, variables)
        return [
            node
            for block in blocks
            if block["web_template"] == template.web_template
            for node in self.nodes(template, dict(variables, block=block))
        ]

    def nodes(self, template, variables: dict, chain: tuple = ()) -> List[dict]:
        chain = chain + (template.name,)
        built = []
        for scope in self.scopes(template, variables):
            node = self.node(template, scope, chain)
            if node:
                built.append(node)
        return built

    def scopes(self, template, variables: dict) -> List[dict]:
        """The variables of each node that the template makes."""
        scopes = [variables]
        if (template.iterate_over or "").strip():
            try:
                rows = evaluate(template.iterate_over, variables)
                if not isinstance(rows, (list, tuple)):
                    raise TypeError("The result is not a list: {!r}".format(rows))
            except Exception as e:
                self.add_error(template, "iterate_over", e)
                return []
            scopes = [dict(variables, row=row) for row in rows]

        if not (template.condition or "").strip():
            return scopes
        return [scope for scope in scopes if self.is_true(template, scope)]

    def is_true(self, template, variables: dict) -> bool:
        try:
            return bool(evaluate(template.condition, variables))
        except Exception as e:
            self.add_error(template, "condition", e)
            return False

    def node(self, template, variables: dict, chain: tuple) -> Optional[dict]:
        self.reached.add(template.name)
        values = {}
        for row in template.properties:
            try:
                if (row.condition or "").strip() and not evaluate(row.condition, variables):
                    continue
                value = self.value(row, variables, chain)
                to_json(value)  # a value that cannot be serialised drops only this property
            except Exception as e:
                self.add_error(template, row.property, e)
                continue
            if not is_empty(value):
                values[row.property] = value

        node_id = self.node_id(template, variables)
        if node_id:
            values = dict({"@id": node_id}, **values)
        return dict({"@type": template.schema_type}, **values) if values else None

    def node_id(self, template, variables: dict) -> Optional[str]:
        try:
            node_id = evaluate(template.id_expression, variables)
            return str(node_id) if node_id else None
        except Exception as e:
            self.add_error(template, "@id", e)
            return None

    def value(self, row, variables: dict, chain: tuple):
        if row.value_type == "Constant":
            return row.value
        if row.value_type == "Expression":
            return evaluate(row.value, variables)

        if row.linked_template in chain:
            raise ValueError("Cycle: {}".format(" > ".join(chain + (row.linked_template,))))
        linked = frappe.get_cached_doc(DOCTYPE, row.linked_template)
        if not linked.enabled:
            return None
        nodes = self.nodes(linked, variables, chain)
        if row.value_type == "Template" and len(nodes) == 1:
            return nodes[0]
        return nodes

    def add_error(self, template, prop: str, error: Exception) -> None:
        message = "{}: {}".format(type(error).__name__, error)
        self.errors.append(BuildError(template.name, prop, message))


def merge_by_id(nodes: List[dict]) -> List[dict]:
    """Joins nodes that have the same `@id`. The first value of each key stays."""
    merged, by_id = [], {}
    for node in nodes:
        first = by_id.get(node.get("@id"))
        if first is None:
            merged.append(node)
            if node.get("@id"):
                by_id[node["@id"]] = node
            continue
        for key, value in node.items():
            first.setdefault(key, value)
    return merged


def is_empty(value) -> bool:
    return value is None or (isinstance(value, (str, list, tuple, dict)) and not value)


def json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError("{} cannot be in JSON".format(type(value).__name__))
