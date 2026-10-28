# Copyright (c) 2020, Rohit Industries Group Private Limited and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.query_builder.functions import IfNull
from frappe.utils import add_days, add_months, flt, getdate, nowdate
from ....utils.item_attribute_utils import attribute_filters, attribute_sort_key, chunks, \
    get_attribute_map
from ....utils.report_utils import blank_zeros
from ....utils.stock_utils import ROL_RARE_MONTHS, compute_rol_for_items, \
    get_consumption_by_window, get_items_for_rol, get_order_lines_for_items, \
    get_rol_consumption_windows, get_rol_data_for_items, get_selling_data_from_lines

# Filter fieldname: attribute. Quality is "<Base Material> Quality".
ATTRIBUTE_FILTERS = [
    ("rm", "Is RM"),
    ("bm", "Base Material"),
    ("tt", "Tool Type"),
    ("series", "Series"),
    ("spl", "Special Treatment"),
    ("purpose", "Purpose"),
    ("type", "Type Selector"),
    ("mtm", "Material to Machine"),
]
SIZE_ATTRIBUTES = ["d1_mm", "w1_mm", "l1_mm", "d2_mm", "l2_mm"]


def execute(filters=None):
    if not filters: filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        "Item:Link/Item:130", "ROL:Float:60", "Auto ROL:Float:70", "ROL Change:Float:70",
        "Value Change:Currency:90", "Change Type::70", "Basis::300", "# SO 12M:Int:60",
        "# Cust 12M:Int:60", "Lead Time:Int:60", "Sold:Float:70", "Sold per Month:Float:70",
        "# Cust:Int:50", "# SO:Int:50", "Consumed:Float:70", "Consumed per Month:Float:70",
        "SR Removed:Float:70", "BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
        "D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60", "D2 MM:Float:50",
        "L2 MM:Float:60", "Description::450", "Template:Link/Item:150",
    ]


def get_data(filters):
    """
    Returns a row for each item with the ROL the quarterly job would set now (Auto ROL) and its
    sales and consumption in the From and To dates. All items are read with a fixed number of
    queries for each chunk of 1,000 items.
    """
    from_date, to_date = getdate(filters.get("from_date")), getdate(filters.get("to_date"))
    if from_date > to_date:
        frappe.throw("From Date should be before To Date")
    months = max((to_date - from_date).days, 1) / 30

    item_dict = {itm.name: itm for itm in get_item_list(filters)}
    quality = "%s Quality" % filters.get("bm")
    att_map = get_attribute_map(item_dict, ["Base Material", "Brand", quality, "Tool Type",
        "Special Treatment"] + SIZE_ATTRIBUTES)
    sort_attributes = ["Base Material", quality, "Tool Type", "d1_mm", "w1_mm", "d2_mm", "l2_mm"]
    names = sorted(item_dict, key=lambda name: attribute_sort_key(att_map.get(name, {}),
        sort_attributes, set(SIZE_ATTRIBUTES)))

    # The period includes the To Date. The Sales Order lines and the consumption of the period
    # and of the windows of the Auto ROL are read with one query each.
    period_to = add_days(to_date, 1)
    rol_from = add_months(to_date, -ROL_RARE_MONTHS)
    windows = get_rol_consumption_windows(to_date)
    windows["period"] = (from_date, period_to)
    data = []
    for chunk in chunks(names):
        items = get_items_for_rol(chunk)
        consumption = get_consumption_by_window(chunk, windows)
        lines = get_order_lines_for_items(chunk, min(from_date, rol_from), period_to)
        rol_lines = {item: [line for line in item_lines
            if rol_from <= line.transaction_date < to_date] for item, item_lines in lines.items()}
        new_rols = compute_rol_for_items(items, to_date=to_date, consumption=consumption,
            order_lines=rol_lines)
        frequency = get_selling_data_from_lines(lines, add_months(to_date, -12), to_date)
        period_data = get_rol_data_for_items(items, period=months, to_date=period_to,
            from_date=from_date, consumption=consumption["period"],
            selling=get_selling_data_from_lines(lines, from_date, period_to))
        for itm in items:
            data.append(get_row(itm, item_dict[itm.name], new_rols[itm.name],
                frequency.get(itm.name, {}), period_data[itm.name], att_map.get(itm.name, {}),
                quality))
    return data


def get_row(itm, desc, new_rol_tuple, freq, rol_data, values, quality):
    new_rol, basis, ch_type = new_rol_tuple
    row = [
        itm.name, itm.existing_rol, new_rol, new_rol - itm.existing_rol,
        (new_rol - itm.existing_rol) * flt(itm.valuation_rate), ch_type, basis,
        freq.get("no_of_so"), freq.get("no_of_customers"), itm.lead_time_days,
        rol_data.sold, rol_data.sold_avg, rol_data.customers, rol_data.no_of_so,
        rol_data.consumed, rol_data.con_avg, rol_data.sred,
        values.get("Base Material"), values.get("Brand"), values.get(quality),
        values.get("Tool Type"), values.get("Special Treatment"),
    ]
    row += [flt(values[att]) if values.get(att) else None for att in SIZE_ATTRIBUTES]
    row += [desc.description, desc.variant_of]
    return blank_zeros(row)


def get_item_list(filters):
    """
    Returns the Items for the filters which are not past their End of Life
    """
    it = frappe.qb.DocType("Item")
    values = {attribute: filters.get(fieldname) for fieldname, attribute in ATTRIBUTE_FILTERS}
    values["%s Quality" % filters.get("bm")] = filters.get("quality")
    query = (
        frappe.qb.from_(it)
        .select(it.name, it.description, it.variant_of)
        .where(IfNull(it.end_of_life, "2099-12-31") > nowdate())
        .where(attribute_filters(it.name, values))
    )
    if filters.get("item"):
        query = query.where(it.name == filters["item"])
    if filters.get("template"):
        query = query.where(it.variant_of == filters["template"])
    return query.run(as_dict=True)
