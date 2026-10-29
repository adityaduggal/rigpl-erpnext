import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.manufacturing_rigpl.utils import job_card_utils as jcu
from rigpl_erpnext.rigpl_erpnext.scheduled_tasks import update_job_card_status as ujs
from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.batch_write_utils import bulk_set_fields

ITEM_1 = "_Test RIGPL UJS Item 1"
ITEM_2 = "_Test RIGPL UJS Item 2"


def d(**kwargs):
    return frappe._dict(kwargs)


class TestBulkSetFields(FrappeTestCase):
    def setUp(self):
        insert_item(ITEM_1)
        insert_item(ITEM_2)

    def tearDown(self):
        frappe.db.rollback()

    def versions(self, name):
        return frappe.db.count("Version", {"ref_doctype": "Item", "docname": name})

    def test_writes_only_changed_fields_with_one_version(self):
        old = {
            ITEM_1: {"item_name": ITEM_1, "description": None},
            ITEM_2: {"item_name": ITEM_2, "description": None},
        }
        new = {
            ITEM_1: {"item_name": "New Name", "description": "New Description"},
            ITEM_2: {"item_name": ITEM_2, "description": None},
        }
        with assert_max_queries(3, test_case=self):
            changes = bulk_set_fields("Item", new, old)

        self.assertEqual(
            changes, {ITEM_1: [["item_name", ITEM_1, "New Name"], ["description", None, "New Description"]]}
        )
        self.assertEqual(
            frappe.db.get_value("Item", ITEM_1, ["item_name", "description"]), ("New Name", "New Description")
        )
        self.assertEqual(self.versions(ITEM_1), 1)
        self.assertEqual(self.versions(ITEM_2), 0)

    def test_no_queries_when_nothing_changed(self):
        values = {ITEM_1: {"item_name": ITEM_1}}
        with assert_max_queries(0, test_case=self):
            self.assertEqual(bulk_set_fields("Item", values, values), {})

    def test_same_new_values_share_one_update(self):
        old = {ITEM_1: {"description": None}, ITEM_2: {"description": None}}
        new = {ITEM_1: {"description": "Same"}, ITEM_2: {"description": "Same"}}
        with assert_max_queries(1, test_case=self):
            bulk_set_fields("Item", new, old, add_versions=False)
        self.assertEqual(frappe.db.get_value("Item", ITEM_2, "description"), "Same")


class TestJobCardCalculations(FrappeTestCase):
    def test_status(self):
        self.assertEqual(jcu.get_job_card_status(d(docstatus=1)), "Completed")
        self.assertEqual(jcu.get_job_card_status(d(docstatus=2)), "Cancelled")
        self.assertEqual(jcu.get_job_card_status(d(docstatus=0, s_warehouse="")), "Work In Progress")
        self.assertEqual(
            jcu.get_job_card_status(d(docstatus=0, s_warehouse="WH", qty_available=5)), "Work In Progress"
        )
        self.assertEqual(jcu.get_job_card_status(d(docstatus=0, s_warehouse="WH", qty_available=0)), "Open")

    def test_process_sno_uses_the_last_matching_operation(self):
        ops = [
            d(idx=1, operation="Cut", final_operation=0),
            d(idx=2, operation="Grind", final_operation=1),
            d(idx=3, operation="Cut", final_operation=0),
        ]
        self.assertEqual(jcu.get_job_card_process_sno(d(operation="Cut"), bt_operations=ops), (3, 0))
        self.assertEqual(jcu.get_job_card_process_sno(d(operation="Grind"), bt_operations=ops), (2, 1))
        self.assertEqual(jcu.get_job_card_process_sno(d(operation="Coat"), bt_operations=ops), (0, 0))

    def test_row_quantities_from_bins(self):
        rows = [
            d(item_code="RM", source_warehouse="WH1"),
            d(item_code="RM", source_warehouse="WH2", qty_available=7),
        ]
        bins = {("RM", "WH1"): d(actual_qty=10, stock_uom="Kg")}
        totals = {"RM": d(prd_qty=2, on_so=3, on_po=4, planned=1, subcon_qty=5)}

        jcu.update_row_quantities(rows, "source_warehouse", bins, totals)

        self.assertEqual(
            (rows[0].qty_available, rows[0].current_projected_qty, rows[0].projected_qty, rows[0].uom),
            (10, 5, 15, "Kg"),
        )
        # No Bin in WH2, so the row is not changed
        self.assertEqual(rows[1].qty_available, 7)

    def test_moved_qty(self):
        jc = d(name="JC0", s_warehouse="WIP")
        submitted = [
            d(name="JC1", status="Completed", t_warehouse="WIP", s_warehouse="RM", operation="Cut",
                total_completed_qty=10),
            d(name="JC2", status="Completed", t_warehouse="FG", s_warehouse="WIP", operation="Grind",
                total_completed_qty=4),
            d(name="JC3", status="Cancelled", t_warehouse="WIP", s_warehouse="RM", operation="Coat",
                total_completed_qty=99),
        ]
        grn_rows = {"POI3": [(6, "WIP"), (50, "FG")]}

        qty = jcu.get_moved_qty(jc, submitted, {"Coat"}, {"JC3": "POI3"}, grn_rows)

        # IN 10 - OUT 4 + GRN 6 into WIP
        self.assertEqual(qty, 12)


class TestJobCardView(FrappeTestCase):
    def get_ctx(self, op=None, ps_tables=()):
        op = op or d(name="OP1", operation="Cut", allow_consumption_of_rm=0,
            allow_production_of_wip_materials=0, transfer_entry=0)
        return d(
            ps={"PS1": d(name="PS1", sales_order=None, sales_order_item=None, sno=None, bom_template="BT1")},
            ps_ops={"PS1": [op]},
            bt_ops={"BT1": [d(idx=4, operation="Cut", final_operation=1)]},
            ps_tables={"PS1": set(ps_tables)},
            rows={},
            item_rows={"FG": d(name="FG", stock_uom="Nos", sales_job_work=0)},
            bins={("FG", "WH"): d(actual_qty=-3)},
            so_qty={}, submitted={}, subcon_ops=set(), first_po_item={}, grn_rows={},
        )

    def get_jc(self, **kwargs):
        jc = d(name="JC1", process_sheet="PS1", operation_id="OP1", operation="Cut", production_item="FG",
            sales_order=None, sales_order_item=None, sno=None, s_warehouse="WH", transfer_entry=0,
            allow_consumption_of_rm=0, allow_production_of_wip_materials=0, uom="Nos")
        jc.update(kwargs)
        return jc

    def test_view_has_new_quantities(self):
        view = ujs.get_job_card_view(self.get_jc(), self.get_ctx())

        # A negative Bin qty gives 0
        self.assertEqual((view.qty_available, view.operation_serial_no, view.final_operation), (0, 4, 1))

    def test_structure_change_needs_a_save(self):
        ctx = self.get_ctx()
        self.assertIsNone(ujs.get_job_card_view(self.get_jc(uom="Kg"), ctx))
        self.assertIsNone(ujs.get_job_card_view(self.get_jc(operation_id="OP9"), ctx))
        self.assertIsNone(ujs.get_job_card_view(self.get_jc(transfer_entry=1, s_warehouse=""), ctx))

    def test_rows_not_allowed_need_a_save(self):
        ctx = self.get_ctx()
        ctx.rows = {"JC1": {"rm_consumed": [d(name="R1", item_code="RM")]}}
        self.assertIsNone(ujs.get_job_card_view(self.get_jc(), ctx))

    def test_empty_table_needs_a_save_only_when_the_process_sheet_has_rows(self):
        op = d(name="OP1", operation="Cut", allow_consumption_of_rm=0, allow_production_of_wip_materials=1,
            transfer_entry=0)
        jc = self.get_jc(allow_production_of_wip_materials=1)
        self.assertIsNotNone(ujs.get_job_card_view(jc, self.get_ctx(op)))
        self.assertIsNone(ujs.get_job_card_view(jc, self.get_ctx(op, ps_tables=["item_manufactured"])))

    def test_open_job_cards_use_new_values_last_operation_first(self):
        jcs = [
            d(name="JC1", production_item="FG", operation_serial_no=1),
            d(name="JC2", production_item="FG", operation_serial_no=1),
        ]
        views = {"JC1": d(name="JC1", production_item="FG", operation_serial_no=3)}

        open_jcs = ujs.get_open_job_cards_by_item(jcs, views)

        self.assertEqual([jc.name for jc in open_jcs["FG"]], ["JC1", "JC2"])
        self.assertIs(open_jcs["FG"][0], views["JC1"])

    def test_cast_matches_the_database(self):
        meta = frappe.get_meta(ujs.JC_DOCTYPE)
        self.assertEqual(ujs.cast(meta, "rm_shortage", 12.7), 12)
        self.assertEqual(ujs.cast(meta, "qty_available", 0.1 + 0.2), 0.3)
        self.assertEqual(ujs.cast(meta, "status", "Open"), "Open")
