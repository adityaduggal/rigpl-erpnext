"""
Display helpers for Script Reports.

A report cell shows nothing for a 0 number, so the values that matter are easy to see.
Use `blank_zeros` on each row before it goes into the report data.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Sequence


def blank_if_zero(value: Any) -> Any:
    """Return None for a number that is 0. Return all other values as they are."""
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) and value == 0:
        return None
    return value


def blank_zeros(row: Sequence[Any]) -> List[Any]:
    """Return the row with each 0 number changed to None."""
    return [blank_if_zero(value) for value in row]
