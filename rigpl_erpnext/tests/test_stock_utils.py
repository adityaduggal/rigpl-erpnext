import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.tests.test_variant_table import insert_item
from rigpl_erpnext.utils.stock_utils import (
    cancel_delete_ste_from_name,
    get_existing_rol_for_item,
    get_max_lead_times,
)

# The quotes would break the old '%s' queries
TEMPLATE = "_Test RIGPL O'Brien Template"
VARIANT = "_Test RIGPL O'Brien Variant"
OTHER_VARIANT = "_Test RIGPL O'Brien Variant 2"
DISABLED_VARIANT = "_Test RIGPL O'Brien Variant 3"


def set_lead_time(item_code, days):
    frappe.db.set_value("Item", item_code, "lead_time_days", days, update_modified=False)


class TestStockUtilsQueries(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_existing_rol_reads_item_with_quote(self):
        insert_item(VARIANT, variant_of=TEMPLATE)
        frappe.get_doc(
            doctype="Item Reorder", name=frappe.generate_hash(length=10), parent=VARIANT,
            parenttype="Item", parentfield="reorder_levels", idx=1, warehouse_reorder_level=25,
        ).db_insert()

        self.assertEqual(get_existing_rol_for_item(VARIANT), 25)
        self.assertEqual(get_existing_rol_for_item("_Test RIGPL No Such Item"), 0)

    def test_max_lead_time_of_enabled_sister_variants(self):
        insert_item(TEMPLATE)
        insert_item(VARIANT, variant_of=TEMPLATE)
        insert_item(OTHER_VARIANT, variant_of=TEMPLATE)
        insert_item(DISABLED_VARIANT, variant_of=TEMPLATE, disabled=1)
        set_lead_time(OTHER_VARIANT, 12)
        set_lead_time(DISABLED_VARIANT, 40)

        self.assertEqual(get_max_lead_times(VARIANT), 12)
        self.assertEqual(get_max_lead_times(TEMPLATE), 0)

    def test_cancel_delete_ste_deletes_its_ledger_entries(self):
        ste_name = "_Test RIGPL STE O'Brien"
        frappe.get_doc(doctype="Stock Entry", name=ste_name, docstatus=0,
            stock_entry_type="Material Receipt", purpose="Material Receipt").db_insert()
        for _ in range(2):
            frappe.get_doc(doctype="Stock Ledger Entry", name=frappe.generate_hash(length=10),
                voucher_type="Stock Entry", voucher_no=ste_name, docstatus=1).db_insert()

        cancel_delete_ste_from_name(ste_name)

        self.assertFalse(frappe.db.exists("Stock Entry", ste_name))
        self.assertFalse(frappe.get_all("Stock Ledger Entry", filters={"voucher_no": ste_name}))
