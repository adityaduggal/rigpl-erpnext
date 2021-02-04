from __future__ import unicode_literals
import frappe
from frappe.utils import flt, getdate
from ....utils.stock_utils import get_rol_for_item


def execute(filters=None):
    if not filters: filters = {}

    columns = get_columns(filters)
    data = get_rol_data(filters)

    return columns, data


def get_columns(filters):
    period = filters.get("months").split(",")
    for p in period:
        if flt(p) == 0:
            frappe.throw("Only Numbers above ZERO are allowed in Period. Use Comma Separated Values Like 3,6,9")
        if flt(p) > 99:
            frappe.throw("Max period is 99 months")
    main_it_cols = ["Item:Link/Item:130", "ROL:Int:50", "ROQ:Int:50",
                    "Is RM::60", "BM::60", "Brand::60", "Quality::60", "TT::130", "SPL::50",
                    "D1 MM:Float:50", "W1 MM:Float:50", "L1 MM:Float:60",
                    "D2 MM:Float:50", "L2 MM:Float:60"]
    compare_cols = []
    for d in period:
        compare_cols += ["SI-" + d + ":Int:70", "#C-" + d + ":Int:70", "Con-" + d + ":Int:70", "STE-" + d + ":Int:70",
                         "SR-" + d + ":Int:70", "PO-" + d + ":Int:70", "#PO-" + d + ":Int:70", "CROL-" + d + ":Int:80"]
    desc_cols = ["Description::450", "Template:Link/Item:350"]
    columns = main_it_cols + compare_cols + desc_cols
    return columns


def get_rol_data(filters):
    period = filters.get("months").split(",")
    to_date = filters.get("to_date")
    conditions_it = get_conditions(filters)
    bm = filters.get("bm")
    query = """SELECT it.name, rol.warehouse_reorder_level as rol, rol.warehouse_reorder_qty as roq,
	IFNULL(rm.attribute_value, 'No') as rm, bm.attribute_value as bm,  
	brand.attribute_value as brand, qual.attribute_value as qual, tt.attribute_value as tt,
	spl.attribute_value as spl, IFNULL(d1.attribute_value, "") as d1, IFNULL(w1.attribute_value, "") as w1,
	IFNULL(l1.attribute_value, "") as l1, IFNULL(d2.attribute_value, "") as d2, IFNULL(l2.attribute_value, "") as l2,
	it.description, it.variant_of
	FROM `tabItem` it
		LEFT JOIN `tabItem Reorder` rol ON it.name = rol.parent AND rol.parentfield = 'reorder_levels'
			AND rol.parenttype = 'Item'
		LEFT JOIN `tabItem Variant Attribute` rm ON it.name = rm.parent
			AND rm.attribute = 'Is RM'
		LEFT JOIN `tabItem Variant Attribute` bm ON it.name = bm.parent
			AND bm.attribute = 'Base Material'
		LEFT JOIN `tabItem Variant Attribute` qual ON it.name = qual.parent
			AND qual.attribute = '%s Quality'
		LEFT JOIN `tabItem Variant Attribute` brand ON it.name = brand.parent
			AND brand.attribute = 'Brand'
		LEFT JOIN `tabItem Variant Attribute` series ON it.name = series.parent
			AND series.attribute = 'Series'
		LEFT JOIN `tabItem Variant Attribute` tt ON it.name = tt.parent
			AND tt.attribute = 'Tool Type'
		LEFT JOIN `tabItem Variant Attribute` spl ON it.name = spl.parent
			AND spl.attribute = 'Special Treatment'
		LEFT JOIN `tabItem Variant Attribute` purpose ON it.name = purpose.parent
			AND purpose.attribute = 'Purpose'
		LEFT JOIN `tabItem Variant Attribute` type ON it.name = type.parent
			AND type.attribute = 'Type Selector'
		LEFT JOIN `tabItem Variant Attribute` mtm ON it.name = mtm.parent
			AND mtm.attribute = 'Material to Machine'
		LEFT JOIN `tabItem Variant Attribute` d1 ON it.name = d1.parent
			AND d1.attribute = 'd1_mm'
		LEFT JOIN `tabItem Variant Attribute` w1 ON it.name = w1.parent
			AND w1.attribute = 'w1_mm'
		LEFT JOIN `tabItem Variant Attribute` l1 ON it.name = l1.parent
			AND l1.attribute = 'l1_mm'
		LEFT JOIN `tabItem Variant Attribute` d2 ON it.name = d2.parent
			AND d2.attribute = 'd2_mm'
		LEFT JOIN `tabItem Variant Attribute` l2 ON it.name = l2.parent
			AND l2.attribute = 'l2_mm'
		WHERE
			IFNULL(it.end_of_life, '2099-12-31') > CURDATE() %s
		ORDER BY 
			bm.attribute_value, qual.attribute_value,
			tt.attribute_value, CAST(d1.attribute_value AS DECIMAL(8,3)),
			CAST(w1.attribute_value AS DECIMAL(8,3)), CAST(l1.attribute_value AS DECIMAL(8,3)),
			CAST(d2.attribute_value AS DECIMAL(8,3)), CAST(l2.attribute_value AS DECIMAL(8,3)),
			brand.attribute_value, spl.attribute_value""" % (bm, conditions_it)
    data = []
    items = frappe.db.sql(query, as_dict=1)
    row = {}
    for it in items:
        row = []
        row = [it.name, it.rol, it.roq, it.rm, it.bm, it.brand, it.qual, it.tt, it.spl, it.d1, it.w1, it.l1, it.d2,
               it.l2]
        for d in period:
            rol_data = get_rol_for_item(it.name, period=flt(d), to_date=to_date)
            row += [
                None if rol_data.sold == 0 else rol_data.sold, None if rol_data.customers == 0 else rol_data.customers,
                None if rol_data.consumed == 0 else rol_data.consumed,
                None if rol_data.no_of_ste == 0 else rol_data.no_of_ste, None if rol_data.sred == 0 else rol_data.sred,
                None if rol_data.purchased == 0 else rol_data.purchased,
                None if rol_data.no_of_po == 0 else rol_data.no_of_po,
                None if rol_data.calculated_rol == 0 else rol_data.calculated_rol
            ]
        row += [it.description, it.variant_of]
        data.append(row)
    return data


def get_conditions(filters):
    conditions_it = ""

    if filters.get("item"):
        conditions_it += " AND it.name = '%s'" % filters.get("item")

    if filters.get("rm"):
        conditions_it += " AND rm.attribute_value = '%s'" % filters.get("rm")

    if filters.get("bm"):
        conditions_it += " AND bm.attribute_value = '%s'" % filters.get("bm")

    if filters.get("series"):
        conditions_it += " AND series.attribute_value = '%s'" % filters.get("series")

    if filters.get("quality"):
        conditions_it += " AND qual.attribute_value = '%s'" % filters.get("quality")

    if filters.get("spl"):
        conditions_it += " AND spl.attribute_value = '%s'" % filters.get("spl")

    if filters.get("purpose"):
        conditions_it += " AND purpose.attribute_value = '%s'" % filters.get("purpose")

    if filters.get("type"):
        conditions_it += " AND type.attribute_value = '%s'" % filters.get("type")

    if filters.get("mtm"):
        conditions_it += " AND mtm.attribute_value = '%s'" % filters.get("mtm")

    if filters.get("tt"):
        conditions_it += " AND tt.attribute_value = '%s'" % filters.get("tt")

    return conditions_it
