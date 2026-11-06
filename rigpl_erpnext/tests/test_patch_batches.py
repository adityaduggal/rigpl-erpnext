"""The v13 patches that write many rows do it in batches (#141). Also the Website Item name length setters."""
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.patches.v13 import update_leave_type_in_attendance
from rigpl_erpnext.patches.v13.fix_long_item_names import (
    WEBSITE_ITEM,
    WEBSITE_ITEM_NAME_FIELDS,
    add_website_item_length_setters,
    setter_name,
)
from rigpl_erpnext.patches.v13.fix_shared_website_item_routes import move_item_website_item_groups
from rigpl_erpnext.tests.test_variant_table import insert_item, insert_website_item
from rigpl_erpnext.website_rigpl.route_sync import add_redirects

ITEM = "_Test RIGPL PATCH-WIG"
WEB_ITEM = "_Test RIGPL PATCH-WIG-W"
NO_WEB_ITEM = "_Test RIGPL PATCH-NO-WEB"
EMPLOYEE = "_Test RIGPL PATCH-EMP"
UPDATEDB = "frappe.database.mariadb.database.MariaDBDatabase.updatedb"


def warm_up(*doctypes):
    """Load the meta and table columns first, so a query guard counts only the batch."""
    for doctype in doctypes:
        frappe.get_all(doctype, limit=1)


def insert_group_row(parent, parenttype, item_group, idx):
    name = frappe.generate_hash(length=10)
    frappe.get_doc(
        {
            "doctype": "Website Item Group",
            "name": name,
            "parent": parent,
            "parenttype": parenttype,
            "parentfield": "website_item_groups",
            "item_group": item_group,
            "idx": idx,
        }
    ).db_insert()
    return name


class TestAddRedirects(FrappeTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def redirects(self):
        return frappe.get_all(
            "Website Route Redirect",
            filters={"source": ("in", [r"test\-rigpl\-patch\-a", r"test\-rigpl\-patch\-b"])},
            fields=["source", "target", "idx", "parent", "parentfield"],
            order_by="idx",
        )

    def test_adds_new_rows_once_with_next_idx(self):
        count = frappe.db.count("Website Route Redirect")
        pairs = [("test-rigpl-patch-a", "new-a"), ("test-rigpl-patch-b", "new-b"), ("test-rigpl-patch-a", "x")]
        warm_up("Website Route Redirect")
        with assert_max_queries(2, test_case=self):
            self.assertEqual(add_redirects(pairs), 2)

        rows = self.redirects()
        self.assertEqual([(r.source, r.target) for r in rows],
            [(r"test\-rigpl\-patch\-a", "/new-a"), (r"test\-rigpl\-patch\-b", "/new-b")])
        self.assertEqual([r.idx for r in rows], [count + 1, count + 2])
        self.assertEqual({(r.parent, r.parentfield) for r in rows}, {("Website Settings", "route_redirects")})

        self.assertEqual(add_redirects(pairs), 0)


class TestMoveWebsiteItemGroups(FrappeTestCase):
    def setUp(self):
        insert_item(ITEM)
        insert_website_item(WEB_ITEM, ITEM)
        insert_group_row(WEB_ITEM, "Website Item", "_Test RIGPL G1", 3)
        self.duplicate = insert_group_row(ITEM, "Item", "_Test RIGPL G1", 1)
        self.moved = insert_group_row(ITEM, "Item", "_Test RIGPL G2", 2)
        self.repeated = insert_group_row(ITEM, "Item", "_Test RIGPL G2", 3)
        self.orphan = insert_group_row(NO_WEB_ITEM, "Item", "_Test RIGPL G1", 1)

    def tearDown(self):
        frappe.db.rollback()

    def test_moves_new_groups_and_deletes_the_rest(self):
        warm_up("Website Item", "Website Item Group")
        with assert_max_queries(6, test_case=self):
            move_item_website_item_groups()

        for name in (self.duplicate, self.repeated, self.orphan):
            self.assertFalse(frappe.db.exists("Website Item Group", name))
        moved = frappe.db.get_value(
            "Website Item Group", self.moved, ["parent", "parenttype", "parentfield", "idx"], as_dict=True
        )
        self.assertEqual(
            moved, {"parent": WEB_ITEM, "parenttype": "Website Item", "parentfield": "website_item_groups", "idx": 4}
        )

        with assert_max_queries(1, test_case=self):
            move_item_website_item_groups()


class TestLeaveTypeInAttendance(FrappeTestCase):
    def setUp(self):
        self.on_leave = self.insert_attendance("2001-01-05")
        self.no_leave = self.insert_attendance("2001-02-05")
        self.insert_leave("Casual Leave", "2001-01-01", "2001-01-10", "2001-01-01 10:00:00")
        self.insert_leave("Sick Leave", "2001-01-04", "2001-01-06", "2001-01-03 10:00:00")
        self.insert_leave("Privilege Leave", "2001-01-01", "2001-01-31", "2001-01-09 10:00:00", status="Rejected")

    def tearDown(self):
        frappe.db.rollback()

    def insert_attendance(self, date):
        name = frappe.generate_hash(length=10)
        frappe.get_doc(
            {
                "doctype": "Attendance",
                "name": name,
                "employee": EMPLOYEE,
                "attendance_date": date,
                "status": "On Leave",
                "docstatus": 1,
            }
        ).db_insert()
        return name

    def insert_leave(self, leave_type, from_date, to_date, modified, status="Approved"):
        frappe.get_doc(
            {
                "doctype": "Leave Application",
                "name": frappe.generate_hash(length=10),
                "employee": EMPLOYEE,
                "leave_type": leave_type,
                "from_date": from_date,
                "to_date": to_date,
                "status": status,
                "docstatus": 1,
                "creation": modified,
                "modified": modified,
            }
        ).db_insert()

    def test_last_modified_approved_leave_sets_the_type(self):
        warm_up("Attendance", "Leave Application")
        with assert_max_queries(10, test_case=self):
            update_leave_type_in_attendance.execute()

        self.assertEqual(frappe.db.get_value("Attendance", self.on_leave, "leave_type"), "Sick Leave")
        self.assertFalse(frappe.db.get_value("Attendance", self.no_leave, "leave_type"))


class TestWebsiteItemLengthSetters(FrappeTestCase):
    def setUp(self):
        frappe.db.delete(
            "Property Setter",
            {"doc_type": WEBSITE_ITEM, "property": "length", "field_name": ("in", WEBSITE_ITEM_NAME_FIELDS)},
        )
        frappe.clear_cache(doctype=WEBSITE_ITEM)

    def tearDown(self):
        frappe.db.rollback()
        frappe.clear_cache(doctype=WEBSITE_ITEM)

    def test_missing_setters_give_both_fields_length_255(self):
        with patch(UPDATEDB):
            add_website_item_length_setters()
        meta = frappe.get_meta(WEBSITE_ITEM)
        self.assertEqual([meta.get_field(field).length for field in WEBSITE_ITEM_NAME_FIELDS], [255, 255])

    def test_existing_table_is_synced_when_setters_are_added(self):
        with patch(UPDATEDB) as updatedb:
            add_website_item_length_setters()
        updatedb.assert_called_once_with(WEBSITE_ITEM)

    def test_no_table_sync_before_website_item_exists(self):
        # A v12 database has no Website Item DocType when the before_migrate hook runs.
        frappe.db.delete("DocType", {"name": WEBSITE_ITEM})
        with patch(UPDATEDB) as updatedb:
            add_website_item_length_setters()
        updatedb.assert_not_called()
        for field in WEBSITE_ITEM_NAME_FIELDS:
            self.assertTrue(frappe.db.exists("Property Setter", setter_name(field)))

    def test_second_run_changes_nothing(self):
        with patch(UPDATEDB):
            add_website_item_length_setters()
        with patch(UPDATEDB) as updatedb:
            add_website_item_length_setters()
        updatedb.assert_not_called()
