# -*- coding: utf-8 -*-
# Copyright (c) 2015, Rohit Industries Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import cint, cstr, comma_and, flt


class CreateBulkProcessSheet(Document):
    def clear_table(self, table_name):
        self.set(table_name, [])

    def clear_all_tables(self):
        tables = ["sales_orders", "items"]
        for d in tables:
            self.clear_table(d)

    @frappe.whitelist()
    def get_open_sales_orders(self):
        """
        Fills the Sales Orders and Items tables with the SO rows that match the filters
        """
        so = frappe.qb.DocType("Sales Order")
        soi = frappe.qb.DocType("Sales Order Item")
        item = frappe.qb.DocType("Item")
        query = (
            frappe.qb.from_(so)
            .join(soi).on(soi.parent == so.name)
            .join(item).on(item.name == soi.item_code)
            .select(
                so.name, so.transaction_date, so.customer, soi.item_code, soi.description,
                soi.qty, soi.delivered_qty, soi.name.as_("soi_name"),
                item.include_item_in_manufacturing, item.made_to_order,
            )
            .where(so.docstatus == 1)
            .orderby(so.transaction_date)
            .orderby(so.name)
        )
        if self.pull_non_pending_sales_orders == 1:
            if not self.sales_order:
                frappe.throw("Sales Order is Mandatory to pull Non-Pending SO")
            query = query.select(soi.qty.as_("pend_qty")).where(so.name == self.sales_order)
        else:
            # Pull sales orders which are pending to deliver based on criteria selected
            query = (
                query.select((soi.qty - soi.delivered_qty).as_("pend_qty"))
                .where(so.status != "Closed")
                .where(soi.qty > soi.delivered_qty)
            )
            if self.sales_order:
                query = query.where(so.name == self.sales_order)
            if self.from_date:
                query = query.where(so.transaction_date >= self.from_date)
            if self.to_date:
                query = query.where(so.transaction_date <= self.to_date)
            if self.customer:
                query = query.where(so.customer == self.customer)
            if self.item:
                query = query.where(soi.item_code == self.item)
        self.add_so_in_table(query.run(as_dict=True))

    def add_so_in_table(self, open_so):
        """ Add sales orders in the table"""
        self.clear_all_tables()
        planned = get_planned_qty_map([r["soi_name"] for r in open_so])
        for r in open_so:
            pp_so = self.append('sales_orders', {})
            pp_so.sales_order = r['name']
            pp_so.sales_order_date = cstr(r['transaction_date'])
            pp_so.customer = cstr(r['customer'])

            # Update Item Table
            if r["include_item_in_manufacturing"] == 1 and r["made_to_order"] == 1:
                ppit_so = self.append("items", {})
                ppit_so.item_code = r['item_code']
                ppit_so.description = r['description']
                ppit_so.planned_qty = (r['pend_qty'] - planned.get(r["soi_name"], 0))
                ppit_so.pending_qty = r['pend_qty']
                ppit_so.ordered_qty = r['qty']
                ppit_so.sales_order = r['name']
                ppit_so.sales_order_item = r['soi_name']

    def get_planned_qty(self, so_item):
        return get_planned_qty_map([so_item]).get(so_item, 0)

    @frappe.whitelist()
    def raise_process_sheet(self):
        # It will raise Process Sheet (Draft) for all distinct Items
        items = self.get_production_items()
        pro_list, failed = [], []
        for item in items:
            if item.get("quantity") > 0:
                process_sheet = self.create_process_sheet(item)
                if process_sheet:
                    pro_list.append(process_sheet)
                else:
                    failed.append(item["production_item"])
        if pro_list:
            pro_list = [frappe.get_desk_link("Process Sheet", p) for p in pro_list]
            frappe.msgprint(_("{0} created").format(comma_and(pro_list)))
            self.clear_all_tables()
        else:
            frappe.msgprint(_("No Process Sheet created"))
        if failed:
            frappe.msgprint(
                _("Process Sheet not created for {0}. See the Error Log for the reason.").format(
                    comma_and(failed)
                ),
                title=_("Process Sheet Not Created"),
                indicator="red",
            )

    def get_production_items(self):
        item_details = []
        planned = get_planned_qty_map([d.sales_order_item for d in self.get("items")])
        for d in self.get("items"):
            pending_qty_for_planning = d.pending_qty - planned.get(d.sales_order_item, 0)
            if d.planned_qty > pending_qty_for_planning:
                frappe.throw("For Row # {} in Items Table the Planned Quantity is Greater than Pending Qty Needed for "
                             "Planning which is {}".format(d.idx, pending_qty_for_planning))
            item_dict = {
                "production_item"   : d.item_code,
                "sales_order"		: d.sales_order,
                "description"		: d.description,
                "status"			: "Draft",
                "sales_order_item"	: d.sales_order_item,
                "sno"               : d.idx,
                "quantity"				: d.planned_qty
            }
            item_details.append(item_dict.copy())
        return item_details

    def create_process_sheet(self, item_dict):
        # Create Process Sheet called from Bulk Process Sheet Creation
        pro = frappe.new_doc("Process Sheet")
        pro.flags.ignore_mandatory = True
        pro.update(item_dict)

        frappe.db.savepoint("create_process_sheet")
        try:
            pro.insert()
            return pro.name
        except Exception:
            frappe.db.rollback(save_point="create_process_sheet")
            frappe.log_error(
                title=f"Bulk Process Sheet not created for {item_dict.get('production_item')}"
            )
            return None


def get_planned_qty_map(so_items):
    """
    Returns {Sales Order Item: qty in Process Sheets that are not cancelled} in 1 query
    """
    so_items = [d for d in set(so_items) if d]
    if not so_items:
        return {}
    ps = frappe.qb.DocType("Process Sheet")
    rows = (
        frappe.qb.from_(ps)
        .select(ps.sales_order_item, Sum(ps.quantity).as_("qty"))
        .where(ps.docstatus < 2)
        .where(ps.sales_order_item.isin(so_items))
        .groupby(ps.sales_order_item)
        .run(as_dict=True)
    )
    return {row.sales_order_item: flt(row.qty) for row in rows}

@frappe.whitelist()
def get_so_pending_for_process_sheet(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
    """ Pull sales orders  which are pending to deliver based on criteria selected"""
    so = frappe.qb.DocType("Sales Order")
    soi = frappe.qb.DocType("Sales Order Item")
    return (
        frappe.qb.from_(so)
        .join(soi).on(soi.parent == so.name)
        .select(
            so.name, so.transaction_date, so.customer, soi.item_code, soi.description, soi.qty,
            soi.delivered_qty, soi.name.as_("soi_name"),
            (soi.qty - soi.delivered_qty).as_("pend_qty"),
        )
        .where(so.docstatus == 1)
        .where(so.status != "Closed")
        .where(soi.qty > soi.delivered_qty)
        .where(so.name.like(f"%{cstr(txt)}%"))
        .orderby(so.transaction_date)
        .orderby(so.name)
        .limit(cint(page_len) or 20)
        .offset(cint(start))
        .run(as_dict=as_dict)
    )
