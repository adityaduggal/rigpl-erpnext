from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from rohit_common.utils.query_guard import assert_max_queries

from rigpl_erpnext.hr_rigpl.utils import hr_utils
from rigpl_erpnext.rigpl_erpnext.validations import employee
from rigpl_erpnext.utils.other_utils import calcsum, validate_aadhaar

BR_INDIA = "_Test RIGPL Branch India"
BR_USA = "_Test RIGPL Branch USA"
BR_NONE = "_Test RIGPL Branch No Country"


def aadhaar(base):
    return base + str(calcsum(base))


AADHAAR_X = aadhaar("01234567890")
AADHAAR_Y = aadhaar("01234567891")


def insert_employee(name, branch=BR_INDIA, status="Active", aadhaar_number=AADHAAR_X, bypass=0):
    frappe.get_doc(dict(doctype="Employee", name=name, employee_name=name, first_name=name, status=status,
        branch=branch, aadhaar_number=aadhaar_number, allow_duplicate_aadhaar=bypass, gender="Male",
        date_of_birth="1990-01-01", date_of_joining="2020-01-01", naming_series="EMP/")).db_insert()


def new_employee(**fields):
    doc = frappe.new_doc("Employee")
    doc.update(dict(name="_Test RIGPL Emp New", status="Active", branch=BR_INDIA, aadhaar_number=AADHAAR_Y))
    doc.update(fields)
    return doc


def as_user_with(*roles):
    return patch.object(frappe, "get_roles", return_value=list(roles))


class EmployeeCase(FrappeTestCase):
    def setUp(self):
        for branch, country in ((BR_INDIA, "India"), (BR_USA, "United States"), (BR_NONE, None)):
            frappe.get_doc(dict(doctype="Branch", name=branch, branch=branch, country=country)).db_insert()
        frappe.db.set_value("Country", "India", "aadhaar_applicable", 1, update_modified=False)
        frappe.db.set_value("Country", "United States", "aadhaar_applicable", 0, update_modified=False)
        frappe.local.message_log = []

    def tearDown(self):
        frappe.db.rollback()
        for doctype, name in (("Country", "India"), ("Country", "United States"), ("Branch", BR_INDIA),
                ("Branch", BR_USA), ("Branch", BR_NONE)):
            frappe.clear_document_cache(doctype, name)

    def messages(self):
        return " ".join(str(frappe.parse_json(m).get("message")) for m in frappe.local.message_log)


class TestAutonameAndFormats(EmployeeCase):
    def test_id_is_month_of_joining_series_and_check_digit(self):
        frappe.db.sql("INSERT INTO `tabSeries` (name, current) VALUES ('_Test RIGPL EMP/', 555)")
        doc = frappe._dict(date_of_joining="2026-10-05", naming_series="_Test RIGPL EMP/")
        employee.autoname(doc, None)
        self.assertEqual(doc.name, "2026105557")

    def test_validate_age_relieving_and_department(self):
        doc = new_employee(date_of_birth="2010-01-01", date_of_joining="2026-01-01", department="All Departments")
        with self.assertRaisesRegex(frappe.ValidationError, "under 18"):
            employee.validate(doc, None)
        doc.update(dict(date_of_birth="1990-01-01", relieving_date="2026-06-01"))
        with self.assertRaisesRegex(frappe.ValidationError, "has to be 'LEFT'"):
            employee.validate(doc, None)
        doc.update(dict(relieving_date=None, department=None))
        with self.assertRaisesRegex(frappe.ValidationError, "Department is Mandatory"):
            employee.validate(doc, None)
        doc.department = "All Departments"
        employee.validate(doc, None)
        self.assertEqual((doc.employee_number, doc.employee), (doc.name, doc.name))

    def test_bad_pan(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Invalid PAN"):
            employee.validate(new_employee(date_of_birth="1990-01-01", date_of_joining="2026-01-01",
                department="All Departments", pan_number="ABC123"), None)

    def test_aadhaar_format(self):
        validate_aadhaar(AADHAAR_X)
        for bad in (AADHAAR_X[:-1], AADHAAR_X + "1", AADHAAR_X[:-1] + str((int(AADHAAR_X[-1]) + 1) % 10), "", None,
                "1234 5678 9012"):
            with self.assertRaises(frappe.ValidationError, msg=bad):
                validate_aadhaar(bad)


class TestAadhaarRules(EmployeeCase):
    def test_branch_without_country(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Set the Country in"):
            employee.validate_aadhaar_rules(new_employee(branch=BR_NONE))
        insert_employee("_Test RIGPL Emp Old", branch=BR_NONE, aadhaar_number=None)
        employee.validate_aadhaar_rules(frappe.get_doc("Employee", "_Test RIGPL Emp Old"))
        self.assertIn("Set the Country in", self.messages())

    def test_aadhaar_only_where_applicable(self):
        with self.assertRaisesRegex(frappe.ValidationError, "Aadhaar Number is mandatory"):
            employee.validate_aadhaar_rules(new_employee(aadhaar_number=None))
        with self.assertRaisesRegex(frappe.ValidationError, "Invalid Aadhaar"):
            employee.validate_aadhaar_rules(new_employee(aadhaar_number="123"))
        employee.validate_aadhaar_rules(new_employee(branch=BR_USA, aadhaar_number=None))
        employee.validate_aadhaar_rules(new_employee(branch=BR_USA, aadhaar_number="123"))

    def test_duplicate_warns_but_saves(self):
        insert_employee("_Test RIGPL Emp Left", status="Left", aadhaar_number=AADHAAR_Y)
        employee.validate_aadhaar_rules(new_employee())
        self.assertNotIn("same Aadhaar", self.messages())
        insert_employee("_Test RIGPL Emp Active", aadhaar_number=AADHAAR_Y)
        employee.validate_aadhaar_rules(new_employee())
        self.assertIn("same Aadhaar", self.messages())
        self.assertIn("_Test RIGPL Emp Active", self.messages())

    def test_only_system_manager_sets_the_bypass(self):
        with as_user_with("HR User"):
            employee.check_bypass_change(new_employee())
            with self.assertRaisesRegex(frappe.ValidationError, "Only a System Manager"):
                employee.check_bypass_change(new_employee(allow_duplicate_aadhaar=1))
            insert_employee("_Test RIGPL Emp Old")
            doc = frappe.get_doc("Employee", "_Test RIGPL Emp Old")
            doc.load_doc_before_save()
            employee.check_bypass_change(doc)
            doc.allow_duplicate_aadhaar = 1
            with self.assertRaisesRegex(frappe.ValidationError, "Only a System Manager"):
                employee.check_bypass_change(doc)
        with as_user_with("System Manager"):
            employee.check_bypass_change(doc)


class TestAadhaarBlock(EmployeeCase):
    def setUp(self):
        super().setUp()
        insert_employee("_Test RIGPL Emp A")
        insert_employee("_Test RIGPL Emp B")
        insert_employee("_Test RIGPL Emp C", status="Left")
        insert_employee("_Test RIGPL Emp D", aadhaar_number=AADHAAR_Y)
        insert_employee("_Test RIGPL Emp E", status="Left", aadhaar_number=AADHAAR_Y)
        insert_employee("_Test RIGPL Emp F", branch=BR_USA)

    def test_only_active_duplicates_block(self):
        blocked = hr_utils.get_aadhaar_blocked(["_Test RIGPL Emp {}".format(c) for c in "ABCDEF"])
        self.assertEqual(blocked, {
            "_Test RIGPL Emp A": ["_Test RIGPL Emp B", "_Test RIGPL Emp F"],
            "_Test RIGPL Emp B": ["_Test RIGPL Emp A", "_Test RIGPL Emp F"],
        })

    def test_bypass_unblocks_only_that_employee(self):
        frappe.db.set_value("Employee", "_Test RIGPL Emp A", "allow_duplicate_aadhaar", 1)
        blocked = hr_utils.get_aadhaar_blocked(["_Test RIGPL Emp A", "_Test RIGPL Emp B"])
        self.assertEqual(list(blocked), ["_Test RIGPL Emp B"])

    def test_attendance_and_salary_slip_are_blocked(self):
        with self.assertRaisesRegex(frappe.ValidationError, "before any Attendance"):
            hr_utils.validate_attendance(frappe._dict(employee="_Test RIGPL Emp A"), None)
        with self.assertRaisesRegex(frappe.ValidationError, "before any Salary Slip"):
            hr_utils.validate_salary_slip(frappe._dict(employee="_Test RIGPL Emp B"), None)
        hr_utils.validate_attendance(frappe._dict(employee="_Test RIGPL Emp D"), None)
        hr_utils.validate_salary_slip(frappe._dict(employee="_Test RIGPL Emp F"), None)

    def test_payroll_entry_drops_only_the_blocked(self):
        doc = frappe.get_doc(dict(doctype="Payroll Entry", employees=[dict(employee="_Test RIGPL Emp {}".format(c))
            for c in "ABDF"]))
        hr_utils.validate_payroll_entry(doc, None)
        self.assertEqual([row.employee for row in doc.employees], ["_Test RIGPL Emp D", "_Test RIGPL Emp F"])
        self.assertEqual([row.idx for row in doc.employees], [1, 2])
        self.assertEqual(doc.number_of_employees, 2)
        self.assertIn("Removed from this Payroll Entry", self.messages())

    def test_query_count_does_not_depend_on_employees(self):
        hr_utils.get_aadhaar_blocked(["_Test RIGPL Emp A"])
        with assert_max_queries(4, test_case=self):
            hr_utils.get_aadhaar_blocked(["_Test RIGPL Emp {}".format(c) for c in "ABCDEF"])
