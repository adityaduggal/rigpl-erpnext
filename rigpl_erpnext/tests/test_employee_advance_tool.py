"""
Employee Advance Tool for an HR User (#231). The advances are inserted with ignore_permissions (HR User cannot
create an Employee Advance or a Journal Entry), so the tool must refuse an Employee outside the User Permissions.
"""
from unittest.mock import patch

import frappe
from frappe.model.document import Document

from rigpl_erpnext.hr_rigpl.doctype.employee_advance_tool.employee_advance_tool import (
    EmployeeAdvanceTool, get_employees)
from rigpl_erpnext.tests.test_selling_reports import ReportTestCase, raw

USER = "_test_rigpl_adv_tool@example.com"
DEPT, OTHER_DEPT = "_Test RIGPL Adv Tool Dept", "_Test RIGPL Adv Tool Other Dept"
EMP, HIDDEN = "_Test RIGPL Adv Tool Employee", "_Test RIGPL Adv Tool Hidden Employee"


class TestEmployeeAdvanceTool(ReportTestCase):
    def setUp(self):
        for lft, dept in ((900011, DEPT), (900013, OTHER_DEPT)):
            raw("Department", name=dept, department_name=dept, is_group=0, lft=lft, rgt=lft + 1)
        for emp, dept in ((EMP, DEPT), (HIDDEN, OTHER_DEPT)):
            raw("Employee", name=emp, employee_name=emp, first_name=emp, department=dept, status="Active",
                date_of_joining="2020-01-01")
        raw("User", name=USER, email=USER, first_name="_Test RIGPL Adv Tool", user_type="System User", enabled=1)
        raw("Has Role", parent=USER, parenttype="User", parentfield="roles", role="HR User")
        frappe.clear_cache(user=USER)
        frappe.get_doc(dict(doctype="User Permission", user=USER, allow="Department", for_value=DEPT,
            apply_to_all_doctypes=1)).insert(ignore_permissions=True)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_permitted_employee(self):
        frappe.set_user(USER)
        self.assertEqual(set(get_employees([EMP])), {EMP})

    def test_employee_of_other_department_is_refused(self):
        frappe.set_user(USER)
        with self.assertRaises(frappe.PermissionError):
            get_employees([EMP, HIDDEN])

    def test_advance_and_journal_entry_skip_doctype_permission(self):
        tool = frappe.get_doc(dict(doctype="Employee Advance Tool", company="_Test Company", advance_account="x"))
        row = frappe._dict(employee=EMP, loan_amount=1000, emi=500)
        with patch.object(Document, "insert") as insert:
            tool.make_advance(row, frappe._dict(employee_name=EMP))
        insert.assert_called_once_with(ignore_permissions=True)
        advance = frappe._dict(employee=EMP, advance_amount=1000, name="x")
        with patch.object(Document, "insert") as insert, \
                patch.object(EmployeeAdvanceTool, "get_voucher_type", return_value="Journal Entry"), \
                patch("erpnext.get_default_cost_center", return_value=None):
            tool.make_journal_entry([advance])
        insert.assert_called_once_with(ignore_permissions=True)
