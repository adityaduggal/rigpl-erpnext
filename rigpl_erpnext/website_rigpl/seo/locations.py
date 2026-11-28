"""
The locations of the company for `LocalBusiness` (#272). A location is an Address of SEO
Settings > Company Addresses. The coordinates come from the Address. The opening hours come
from the newest file `working_hours_<address name>*.csv` of the Address. The weekly off day
and the holidays come from the default Holiday List of the Company.
"""
from __future__ import annotations

import csv
import io
import re
from typing import List, Optional

import frappe
from frappe.utils import add_days, escape_html, flt, getdate, nowdate
from frappe.website.render import clear_cache

from .organization import get_address, get_company_name, get_location_names

FILE_PREFIX = "working_hours_"
COLUMNS = ["day", "opens", "closes"]
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
AREA_ROW = "area_served"
TIME = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
# holidays after these days are not output
HOLIDAY_DAYS = 90
CLOSED_TIME = "00:00"


def parse_hours(text: str) -> dict:
    """{"days": {day: (opens, closes)}, "area_served": [names]} of the CSV text. A day with no
    times, or a day with no row, is closed. A bad row raises ValueError with its number."""
    rows = list(csv.reader(io.StringIO((text or "").lstrip("﻿"))))
    if not rows or [cell.strip().lower() for cell in rows[0][:3]] != COLUMNS:
        raise ValueError("Row 1 must be: {}".format(",".join(COLUMNS)))

    days, area = {}, []
    for number, row in enumerate(rows[1:], 2):
        cells = [cell.strip() for cell in row] + ["", "", ""]
        name, opens, closes = cells[:3]
        if not any(cells):
            continue
        if name.lower() == AREA_ROW:
            area = [part.strip() for part in opens.split(";") if part.strip()]
            continue
        day = name.capitalize()
        if day not in DAYS or day in days:
            raise ValueError("Row {}: use each day name one time, or {}".format(number, AREA_ROW))
        if not opens and not closes:
            days[day] = None
            continue
        if not (TIME.match(opens) and TIME.match(closes)):
            raise ValueError("Row {}: write the times as HH:MM".format(number))
        opens, closes = opens.zfill(5), closes.zfill(5)
        if opens >= closes:
            raise ValueError("Row {}: closes must be after opens".format(number))
        days[day] = (opens, closes)
    return {"days": {day: times for day, times in days.items() if times}, "area_served": area}


def get_locations() -> List[dict]:
    """The context value `locations`: one dict for each Address of SEO Settings."""
    names = get_location_names()
    if not names:
        return []
    holidays = get_holidays()
    files = get_hours_files(names)
    return [make_location(name, files.get(name), holidays) for name in names]


def make_location(name: str, file_name: Optional[str], holidays: dict) -> dict:
    address = frappe.get_cached_doc("Address", name)
    hours = read_hours(name, file_name)
    postal = get_address(name)
    return {
        "id": frappe.scrub(name),
        "city": postal["city"],
        "address": postal,
        "telephone": (address.phone or "").split(",")[0].strip(),
        "latitude": flt(address.get("latitude")) or "",
        "longitude": flt(address.get("longitude")) or "",
        "hours": make_opening_hours(hours.get("days") or {}, holidays),
        "area_served": hours.get("area_served") or [address.country],
    }


def make_opening_hours(days: dict, holidays: dict) -> List[dict]:
    """The `OpeningHoursSpecification` rows. No rows when the location has no hours."""
    if not days:
        return []
    by_times = {}
    for day in DAYS:
        if day in days and day != holidays.get("weekly_off"):
            by_times.setdefault(days[day], []).append(day)
    rows = [
        {"days": found, "opens": opens, "closes": closes, "valid_from": "", "valid_through": ""}
        for (opens, closes), found in by_times.items()
    ]
    # a holiday is closed: both times are 00:00
    rows += [
        {"days": [], "opens": CLOSED_TIME, "closes": CLOSED_TIME, "valid_from": date, "valid_through": date}
        for date in holidays.get("dates") or []
    ]
    return rows


def get_holidays() -> dict:
    """The weekly off day and the coming holidays on other days, of the Holiday List of the
    Company."""
    company = get_company_name()
    name = company and frappe.get_cached_value("Company", company, "default_holiday_list")
    if not name:
        return {}
    weekly_off = frappe.get_cached_value("Holiday List", name, "weekly_off") or ""
    today = nowdate()
    filters = {
        "parent": name,
        "parenttype": "Holiday List",
        "holiday_date": ["between", [today, add_days(today, HOLIDAY_DAYS)]],
    }
    dates = frappe.get_all("Holiday", filters=filters, pluck="holiday_date", order_by="holiday_date")
    return {
        "weekly_off": weekly_off,
        "dates": [str(date) for date in dates if getdate(date).strftime("%A") != weekly_off],
    }


def get_hours_files(names: list) -> dict:
    """{address name: File name} of the newest hours file of each Address, in one query."""
    filters = {
        "attached_to_doctype": "Address",
        "attached_to_name": ["in", names],
        "file_name": ["like", FILE_PREFIX.replace("_", "\\_") + "%.csv"],
    }
    rows = frappe.get_all(
        "File",
        filters=filters,
        fields=["name", "file_name", "attached_to_name"],
        order_by="creation desc",
    )
    found = {}
    for row in rows:
        if is_hours_file(row.file_name, row.attached_to_name):
            found.setdefault(row.attached_to_name, row.name)
    return found


def is_hours_file(file_name: str, address: str) -> bool:
    """Frappe can add a suffix before `.csv` to a file name that exists."""
    name = (file_name or "").lower()
    return name.startswith((FILE_PREFIX + (address or "")).lower()) and name.endswith(".csv")


def read_hours(address: str, file_name: Optional[str]) -> dict:
    """An empty dict when there is no file, or when it cannot be read."""
    if not file_name:
        return {}
    try:
        return parse_hours(read_text(frappe.get_doc("File", file_name)))
    except (ValueError, OSError):
        frappe.log_error(frappe.get_traceback(), "Working hours of {}".format(address)[:140])
        return {}


def read_text(file) -> str:
    content = file.get_content()
    return content.decode("utf-8-sig") if isinstance(content, bytes) else content


def validate_hours_file(doc, method=None) -> None:
    """File validate. Stops an upload of an hours file that cannot be read."""
    if doc.attached_to_doctype != "Address" or not (doc.file_name or "").startswith(FILE_PREFIX):
        return
    if not doc.file_name.lower().endswith(".csv"):
        return
    try:
        parse_hours(read_text(doc))
    except (ValueError, UnicodeDecodeError) as e:
        frappe.throw(
            escape_html(str(e)), title="Working hours file", exc=frappe.ValidationError
        )


def clear_hours_cache(doc, method=None) -> None:
    """File on_update and on_trash: the pages show new hours at once."""
    if doc.attached_to_doctype == "Address" and is_hours_file(doc.file_name, doc.attached_to_name):
        clear_cache()


def address_on_update(doc, method=None) -> None:
    if doc.name not in get_location_names():
        return
    warn_missing_coordinates([doc.name])
    clear_cache()


def warn_missing_coordinates(names: list) -> None:
    if not names:
        return
    filters = {"name": ["in", names]}
    rows = frappe.get_all("Address", filters=filters, fields=["name", "latitude", "longitude"])
    missing = [row.name for row in rows if not (flt(row.latitude) and flt(row.longitude))]
    if missing:
        frappe.msgprint(
            "Please update the coordinates of: {}".format(escape_html(", ".join(missing))),
            title="Address without coordinates",
            indicator="orange",
        )
