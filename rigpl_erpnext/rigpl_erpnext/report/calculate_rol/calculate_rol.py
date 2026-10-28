from __future__ import unicode_literals
import frappe
from frappe.utils import add_months, cint, escape_html, flt, fmt_money, getdate
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import compute_rol_for_items, get_items_for_rol, \
    get_rol_data_for_items


def execute(filters=None):
    if not filters: filters = {}

    periods = get_periods(filters)
    columns = get_columns()
    items = get_items_for_rol([filters.get("item")])
    if not items:
        return columns, []
    data = get_rol_data(filters, items[0], periods)
    message = get_rol_message(filters, items[0])

    return columns, data, message


def get_periods(filters):
    """
    Returns the periods in months in ascending order
    """
    periods = []
    for p in filters.get("months").split(","):
        if flt(p) <= 0 or flt(p) != cint(p):
            frappe.throw("Only Whole Numbers above ZERO are allowed in Period. Use Comma Separated "
                "Values Like 3,6,12")
        if flt(p) > 99:
            frappe.throw("Max period is 99 months")
        periods.append(cint(p))
    return sorted(set(periods))


def get_columns():
    return [
        "Period::90", "From Date:Date:90", "To Date:Date:90", "Months:Int:60",
        "Sold:Float:80", "Sold per Month:Float:80", "# Customers:Int:80", "# SO:Int:60",
        "Consumed:Float:80", "Consumed per Month:Float:80", "# STE:Int:60",
        "SR Removed:Float:80", "Purchased:Float:80", "Purchased per Month:Float:80",
        "# PO:Int:60", "Calculated ROL:Float:100",
    ]


def get_rol_data(filters, itm, periods):
    """
    Returns a row for each period. Cumulative periods all end on the To Date (3, 6, 12 months
    before it). Otherwise each period starts where the previous one ends, so for 3,6,12 the
    rows are 0-3, 3-6 and 6-12 months before the To Date.
    """
    to_date = getdate(filters.get("to_date"))
    cumulative = cint(filters.get("cumulative"))
    data = []
    prev_period = 0
    for period in periods:
        if cumulative:
            months, period_to, label = period, to_date, f"{period} Months"
        else:
            months, period_to = period - prev_period, add_months(to_date, -prev_period)
            label = f"{prev_period}-{period} Months"
        period_from = add_months(to_date, -period)
        rol_data = get_rol_data_for_items([itm], period=months, to_date=period_to,
            from_date=period_from)[itm.name]
        data.append(blank_zeros([
            label, period_from, period_to, months,
            rol_data.sold, rol_data.sold_avg, rol_data.customers, rol_data.no_of_so,
            rol_data.consumed, rol_data.con_avg, rol_data.no_of_ste,
            rol_data.sred, rol_data.purchased, rol_data.po_avg, rol_data.no_of_po,
            rol_data.calculated_rol,
        ]))
        prev_period = period
    return data


def get_rol_message(filters, itm):
    """
    Returns the item details and the ROL which the quarterly job would set now
    """
    new_rol, basis, ch_type = compute_rol_for_items([itm], to_date=filters.get("to_date"))[itm.name]
    roq = itm.reorder_rows[0].warehouse_reorder_qty if itm.reorder_rows else 0
    description = frappe.get_cached_value("Item", itm.name, "description")
    return f"""<b>{escape_html(itm.name)}</b>: {escape_html(description or "")}<br>
        Existing ROL = {flt(itm.existing_rol)}, ROQ = {flt(roq)},
        Lead Time = {cint(itm.lead_time_days)} days,
        Valuation Rate = {fmt_money(itm.valuation_rate)}<br>
        <b>Auto ROL = {flt(new_rol)}</b> ({escape_html(ch_type)}) based on {escape_html(basis)}"""
