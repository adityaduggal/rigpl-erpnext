"""
Carrier code -> Carrier Tracking status, from the Shipping Status Map DocType (#168).

- Code rows are checked first, then Code Starts With, then Text Contains. In each kind the
  longest match wins, so "undelivered" wins over "delivered".
- A code with no row, or a row with no status, gives None. The caller keeps the tracking
  open (In Transit) and `StatusResolver.unknown` collects the code, so it can be added to
  the map with an empty status for a user to fill in.
- The map is read once and cached in Redis. A save or delete of a row clears the cache.
"""
import hashlib
from typing import Dict, Iterable, List, Optional, Set, Tuple

import frappe
from frappe.utils import now

CODE, STARTS_WITH, TEXT = "Code", "Code Starts With", "Text Contains"
CACHE_KEY = "rigpl_shipping_status_map"
Rule = Tuple[str, str, str]  # (match_on, carrier_code upper, status)


def rule_name(provider: str, match_on: str, carrier_code: str) -> str:
    key = f"{provider}|{match_on}|{(carrier_code or '').strip().upper()}"
    return f"{provider}-{hashlib.sha1(key.encode()).hexdigest()[:12]}"


def clear_status_map_cache() -> None:
    frappe.cache().delete_value(CACHE_KEY)


def load_rules() -> Dict[str, List[Rule]]:
    """{provider: [rules]} from the DocType: 1 query, then Redis."""
    def fetch():
        rules: Dict[str, List[Rule]] = {}
        for row in frappe.get_all("Shipping Status Map", fields=["provider", "match_on", "carrier_code", "status"]):
            rules.setdefault(row.provider, []).append((row.match_on, (row.carrier_code or "").upper(), row.status or ""))
        return rules

    return frappe.cache().get_value(CACHE_KEY, generator=fetch)


def match(rules: Iterable[Rule], code: str, text: str) -> Optional[Rule]:
    """The best rule for a code and a status text, or None. Pure."""
    code, text = (code or "").strip().upper(), (text or "").upper()
    exact = [r for r in rules if r[0] == CODE and code and r[1] == code]
    if exact:
        return exact[0]
    prefix = [r for r in rules if r[0] == STARTS_WITH and code and code.startswith(r[1])]
    contains = [r for r in rules if r[0] == TEXT and text and r[1] in text]
    for found in (prefix, contains):
        if found:
            return max(found, key=lambda r: len(r[1]))
    return None


class StatusResolver:
    """Resolves the codes of one provider. `rules=None` reads the DocType (tests pass rules)."""

    def __init__(self, provider: str, rules: Optional[List[Rule]] = None):
        self.provider = provider
        self.rules = rules if rules is not None else load_rules().get(provider, [])
        self.unknown: Dict[str, str] = {}  # code -> description

    def __call__(self, code: str, text: str = "") -> Optional[str]:
        rule = match(self.rules, code, text)
        if rule and rule[2]:
            return rule[2]
        if not rule and code:
            self.unknown.setdefault(code.strip().upper(), (text or "")[:140])
        return None


def seed_rules(provider: str, rules: Iterable[Tuple[str, str, str, str]]) -> List[Rule]:
    """The (match_on, code, status, description) seeds of an adapter as Rules, for tests."""
    return [(m, c.upper(), s) for m, c, s, _d in rules]


ROW_FIELDS = ("name", "creation", "modified", "owner", "modified_by", "docstatus", "idx",
              "provider", "match_on", "carrier_code", "status", "description")


def insert_rules(provider: str, rules: Iterable[Tuple[str, str, str, str]], skip: Set[str] = frozenset()) -> int:
    """Adds the rows that are missing: 1 read and 1 insert. An existing row is never changed,
    so a status that a user set stays. Returns the number added."""
    rows, ts, user = [], now(), frappe.session.user
    for match_on, code, status, description in rules:
        name = rule_name(provider, match_on, code)
        if name not in skip:
            rows.append((name, ts, ts, user, user, 0, 0, provider, match_on, code.strip().upper(), status, description))
    if not rows:
        return 0
    existing = set(frappe.get_all("Shipping Status Map", filters={"name": ["in", [r[0] for r in rows]]}, pluck="name"))
    rows = [r for r in rows if r[0] not in existing]
    if rows:
        from ...utils.batch_write_utils import bulk_insert_rows

        bulk_insert_rows("Shipping Status Map", ROW_FIELDS, rows)
        clear_status_map_cache()
    return len(rows)


def record_unknown(resolvers: Iterable[StatusResolver]) -> int:
    """Adds the unknown codes seen in a run, with an empty status, for a user to map."""
    added = 0
    for resolver in resolvers:
        added += insert_rules(resolver.provider, ((CODE, code, "", text) for code, text in resolver.unknown.items()))
    return added
