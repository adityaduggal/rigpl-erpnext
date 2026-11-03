
import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.manufacturing_rigpl.report.bom_templates import bom_templates
from rigpl_erpnext.manufacturing_rigpl.report.process_sheet_analysis import process_sheet_analysis as psa
from rigpl_erpnext.manufacturing_rigpl.report.production_and_planning_report_rigpl import (
    production_and_planning_report_rigpl as ppr,
)
from rigpl_erpnext.manufacturing_rigpl.utils.job_card_utils import pick_last_jc
from rigpl_erpnext.rigpl_erpnext.report.mto_stock_ledger import mto_stock_ledger
from rigpl_erpnext.tests.test_buying_reports import insert_subcontracting_warehouse
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw


def job_card(name, idx, operation, docstatus=1, completed=10):
    return frappe._dict(
        name=name, idx=idx, operation=operation, docstatus=docstatus, total_completed_qty=completed
    )


def po_row(stock_qty, received_qty):
    return frappe._dict(
        name="PO-1", transaction_date="2026-10-01", stock_qty=stock_qty, received_qty=received_qty
    )


class TestPickLastJobCard(FrappeTestCase):
    def test_no_job_card(self):
        self.assertEqual(pick_last_jc([], set(), {}), {})

    def test_all_operations_completed(self):
        rows = [job_card("JC2", 2, "Grinding", completed=8), job_card("JC1", 1, "Cutting")]
        jc = pick_last_jc(rows, set(), {})
        self.assertEqual(jc.name, "JC2")
        self.assertEqual(jc.remarks, " All Operations Completed 8 Qty Ready for Dispatch")

    def test_first_operation_pending(self):
        rows = [job_card("JC1", 1, "Cutting", docstatus=0), job_card("JC2", 2, "Grinding", docstatus=0)]
        jc = pick_last_jc(rows, set(), {})
        self.assertEqual(jc.name, "JC1")
        self.assertEqual(jc.remarks, "Taken into Production but First Process is Pending")

    def test_middle_operation_pending(self):
        rows = [
            job_card("JC1", 1, "Cutting"),
            job_card("JC2", 2, "Grinding", docstatus=0),
            job_card("JC3", 3, "Marking", docstatus=0),
        ]
        jc = pick_last_jc(rows, set(), {})
        self.assertEqual(jc.name, "JC2")
        self.assertEqual(jc.remarks, " Grinding Pending and Cutting Completed")

    def test_open_subcontracting_po_stops_at_its_job_card(self):
        rows = [job_card("JC1", 1, "Coating"), job_card("JC2", 2, "Marking", docstatus=0)]
        jc = pick_last_jc(rows, {"Coating"}, {"JC1": [po_row(10, 6)]})
        self.assertEqual(jc.name, "JC1")
        self.assertIn("PO# ", jc.remarks)
        self.assertIn("Pending Qty= 4 PO Date: 2026-10-01", jc.remarks)

    def test_received_subcontracting_po_goes_on(self):
        rows = [job_card("JC1", 1, "Coating"), job_card("JC2", 2, "Marking", docstatus=0)]
        jc = pick_last_jc(rows, {"Coating"}, {"JC1": [po_row(10, 10)]})
        self.assertEqual(jc.name, "JC2")
        self.assertEqual(jc.remarks, " Marking Pending and Coating Completed")


class TestProcessSheetAnalysis(FrappeTestCase):
    def test_view(self):
        self.assertEqual(psa.get_view(frappe._dict()), "default")
        self.assertEqual(psa.get_view(frappe._dict(pending=1)), "pending")
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(pending=1, process_wise=1, item="X"))
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(rm_used=1))
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(process_wise=1))

    def test_sizes_sort_as_numbers_after_no_value(self):
        numeric = set(psa.SIZE_ATTS)
        sheet = frappe._dict(name="PS1", priority=1, production_item="A")
        no_value = psa.sort_key(sheet, {}, numeric)
        two = psa.sort_key(sheet, {"d1_mm": "2"}, numeric)
        ten = psa.sort_key(sheet, {"d1_mm": "10"}, numeric)
        self.assertLess(no_value, two)
        self.assertLess(two, ten)

    def test_priority_sorts_first(self):
        numeric = set(psa.SIZE_ATTS)
        first = psa.sort_key(frappe._dict(name="PS2", priority=1), {"d1_mm": "10"}, numeric)
        second = psa.sort_key(frappe._dict(name="PS1", priority=2), {"d1_mm": "2"}, numeric)
        self.assertLess(first, second)


class TestProductionPlanningReport(FrappeTestCase):
    def test_view(self):
        self.assertEqual(ppr.get_view(frappe._dict(summary=1)), "summary")
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict())
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(summary=1, mach_eff=1))
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(op_time_analysis=1))
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(mach_eff=1))

    def test_attribute_cells_round_sizes_only(self):
        cells = ppr.get_attribute_cells({"Base Material": "HSS", "d1_mm": "4.50"}, ppr.ATTS)
        self.assertEqual(cells[0], "HSS")
        self.assertEqual(cells[ppr.ATTS.index("d1_mm")], 4.5)
        self.assertIsNone(cells[ppr.ATTS.index("w1_mm")])


class TestBomTemplates(FrappeTestCase):
    def test_restriction_values(self):
        values = bom_templates.get_restriction_values(frappe._dict(bm="HSS", quality="H-3X"))
        self.assertEqual(values, {"Base Material": "HSS", "HSS Quality": "H-3X"})
        self.assertRaises(
            frappe.ValidationError, bom_templates.get_restriction_values, frappe._dict(quality="H-3X")
        )

    def test_missing_restriction_shows_dash(self):
        self.assertEqual(bom_templates.allowed_or_dash(None), "-")
        self.assertEqual(bom_templates.allowed_or_dash(""), "")


MTO_WH = "_Test RIGPL O'MTO WH"
MTO_SUBCON_WH = "_Test RIGPL O'MTO Subcon WH"
MTO_SO_ITEM = "_Test RIGPL O'SO Item"


def insert_mto_job_card(date, s_warehouse, t_warehouse, qty):
    ps = raw("Process Sheet", bom_template="_Test RIGPL O'BT")
    jc = raw("Process Job Card RIGPL", posting_date=date, posting_time="10:00:00.4", production_item="O'Item",
        description="O'Item", total_completed_qty=qty, s_warehouse=s_warehouse, t_warehouse=t_warehouse,
        process_sheet=ps, sales_order_item=MTO_SO_ITEM, docstatus=1, status="Completed")
    raw("Stock Entry", process_job_card=jc)
    return jc


class TestMtoStockLedger(ReportTestCase):
    def test_in_out_and_subcontracting_receipt(self):
        raw("Warehouse", name=MTO_WH, warehouse_name=MTO_WH, short_code="_TOMTO", listing_serial=99, is_group=0)
        insert_subcontracting_warehouse(MTO_SUBCON_WH)
        jc_in = insert_mto_job_card("2026-01-03", None, MTO_WH, 10)
        jc_out = insert_mto_job_card("2026-01-02", MTO_WH, MTO_SUBCON_WH, 4)
        jc_sub = insert_mto_job_card("2026-01-01", "_Test RIGPL O'Other WH", MTO_SUBCON_WH, 4)
        po = raw("Purchase Order", docstatus=1)
        poi = raw("Purchase Order Item", parent=po, parenttype="Purchase Order", parentfield="items",
            reference_dn=jc_sub)
        pr = raw("Purchase Receipt", docstatus=1, posting_date="2026-01-05", posting_time="11:00:00")
        raw("Purchase Receipt Item", parent=pr, parenttype="Purchase Receipt", parentfield="items",
            purchase_order_item=poi, warehouse=MTO_WH, qty=4, description="O'Receipt")
        ste = raw("Stock Entry", purchase_receipt_no=pr)
        filters = frappe._dict(so_item=MTO_SO_ITEM, warehouse=MTO_WH, from_date="2026-01-01")

        data = self.assert_queries(3, lambda: mto_stock_ledger.execute(filters)[1])

        self.assertEqual([(row[4], row[7], row[16]) for row in data], [
            (10, jc_in, "Process Job Card RIGPL"),
            (-4, jc_out, "Process Job Card RIGPL"),
            (4, pr, "Purchase Receipt"),
        ])
        self.assertEqual(str(data[0][1]), "10:00:01")
        self.assertEqual(data[2][10], ste)
