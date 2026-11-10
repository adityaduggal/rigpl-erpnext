
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
        self.assertIn('/app/purchase-order/PO-1" target="_blank">PO-1</a>', jc.remarks)

    def test_received_subcontracting_po_goes_on(self):
        rows = [job_card("JC1", 1, "Coating"), job_card("JC2", 2, "Marking", docstatus=0)]
        jc = pick_last_jc(rows, {"Coating"}, {"JC1": [po_row(10, 10)]})
        self.assertEqual(jc.name, "JC2")
        self.assertEqual(jc.remarks, " Marking Pending and Coating Completed")


PS_USER = "_test_rigpl_ps_analysis@example.com"
PS_ITEM, PS_HIDDEN_ITEM = "_Test RIGPL PSA Item", "_Test RIGPL PSA Hidden Item"
PS_DATE = "2030-01-01"


class TestProcessSheetAnalysis(ReportTestCase):
    def test_view(self):
        self.assertEqual(psa.get_view(frappe._dict()), "default")
        self.assertEqual(psa.get_view(frappe._dict(view="Process Sheets")), "default")
        self.assertEqual(psa.get_view(frappe._dict(view="Pending Process Sheets")), "pending")
        self.assertEqual(psa.get_view(frappe._dict(view="RM Used Details", item="X")), "rm_used")
        self.assertEqual(psa.get_view(frappe._dict(view="Process Wise Details", item="X")), "process_wise")
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(view="RM Used Details"))
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(view="Process Wise Details"))
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(view="Unknown"))
        self.assertRaises(frappe.ValidationError, psa.get_view, frappe._dict(view=["!=", ""]))

    def insert_sheets(self):
        for item in (PS_ITEM, PS_HIDDEN_ITEM):
            raw("Item", name=item, item_code=item, item_name=item, item_group="All Item Groups", stock_uom="Nos")
            # User Permission on Item applies to every Item link field, so best_rm_item must match too
            raw("Process Sheet", production_item=item, best_rm_item=item, docstatus=1, status="Submitted", quantity=10,
                produced_qty=0, date=PS_DATE, priority=1, description=item)

    def test_user_sees_only_permitted_process_sheets(self):
        self.insert_sheets()
        raw("User", name=PS_USER, email=PS_USER, first_name="_Test RIGPL PSA", user_type="System User", enabled=1)
        raw("Has Role", parent=PS_USER, parenttype="User", parentfield="roles", role="Production Inventory User")
        frappe.clear_cache(user=PS_USER)
        frappe.get_doc(dict(doctype="User Permission", user=PS_USER, allow="Item", for_value=PS_ITEM,
            apply_to_all_doctypes=1)).insert(ignore_permissions=True)
        for view in ("Process Sheets", "Pending Process Sheets"):
            filters = frappe._dict(view=view, status="Submitted")
            self.assertEqual(self.items(filters, "Administrator"), {PS_ITEM, PS_HIDDEN_ITEM})
            self.assertEqual(self.items(filters, PS_USER), {PS_ITEM})

    def items(self, filters, user):
        col = 4 if filters.view == "Pending Process Sheets" else 3
        frappe.set_user(user)
        try:
            return {row[col] for row in psa.execute(filters)[1] if row[col] in (PS_ITEM, PS_HIDDEN_ITEM)}
        finally:
            frappe.set_user("Administrator")

    def test_rm_used_shows_sheet_of_another_production_item(self):
        self.insert_sheets()
        sheet = frappe.db.get_value("Process Sheet", {"production_item": PS_ITEM}, "name")
        raw("Process Sheet Items", parent=sheet, parenttype="Process Sheet", parentfield="rm_consumed",
            item_code=PS_HIDDEN_ITEM, calculated_qty=30, qty=0, donot_consider_rm_for_production=0)
        rows = psa.execute(frappe._dict(view="RM Used Details", item=PS_HIDDEN_ITEM))[1]
        self.assertEqual([(row[0], row[2], row[4]) for row in rows], [(sheet, PS_HIDDEN_ITEM, 30)])

    def test_queries_do_not_grow_with_rows(self):
        self.insert_sheets()
        filters = frappe._dict(view="Pending Process Sheets", item=PS_ITEM)
        self.assert_queries(8, lambda: psa.execute(filters))

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
        self.assertEqual(ppr.get_view(frappe._dict(view="Post Production Summary")), "summary")
        self.assertEqual(ppr.get_view(frappe._dict(view="Production Planning")), "production_planning")
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict())
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(view="summary"))
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(view=["!=", ""]))
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(view="Operation Time Analysis"))
        self.assertRaises(frappe.ValidationError, ppr.get_view, frappe._dict(view="Machine Efficiency"))

    def test_attribute_cells_round_sizes_only(self):
        cells = ppr.get_attribute_cells({"Base Material": "HSS", "d1_mm": "4.50"}, ppr.ATTS)
        self.assertEqual(cells[0], "HSS")
        self.assertEqual(cells[ppr.ATTS.index("d1_mm")], 4.5)
        self.assertIsNone(cells[ppr.ATTS.index("w1_mm")])


FAN_OUT_WS = "_Test RIGPL Fan-out WS"
FAN_OUT_ITEM = "_Test RIGPL Fan-out Item"
FAN_OUT_DATE = "2030-01-01"


class TestTimeLogFanOut(ReportTestCase):
    """A Job Card with 2 time logs must count once, as with 1 time log."""

    def setUp(self):
        raw("Workstation", name=FAN_OUT_WS, workstation_name=FAN_OUT_WS, hour_rate=60)
        raw("Item", name=FAN_OUT_ITEM, item_code=FAN_OUT_ITEM, item_name=FAN_OUT_ITEM)
        self.jc = raw("Process Job Card RIGPL", docstatus=1, posting_date=FAN_OUT_DATE, workstation=FAN_OUT_WS,
            production_item=FAN_OUT_ITEM, operation="_Test RIGPL Op", for_quantity=10, total_completed_qty=10,
            total_rejected_qty=0, total_time_in_mins=60)
        for hour in ("10", "11"):
            raw("Job Card Time Log", parent=self.jc, parenttype="Process Job Card RIGPL", parentfield="time_logs",
                from_time="%s %s:00:00" % (FAN_OUT_DATE, hour), to_time="%s %s:30:00" % (FAN_OUT_DATE, hour),
                time_in_mins=30)

    def test_machine_efficiency_hours(self):
        filters = frappe._dict(view="Machine Efficiency", mach_eff_type="Total", from_date=FAN_OUT_DATE,
            to_date=FAN_OUT_DATE)
        rows = [row for row in ppr.execute(filters)[1] if row[0] == FAN_OUT_WS]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][3], 1)

    def test_op_time_analysis_one_row(self):
        filters = frappe._dict(view="Operation Time Analysis", operation="_Test RIGPL Op", item=FAN_OUT_ITEM,
            from_date=FAN_OUT_DATE, to_date=FAN_OUT_DATE)
        data = ppr.execute(filters)[1]
        self.assertEqual([row[-2] for row in data], [self.jc])


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
