# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import cint, getdate, split_emails
from dateutil.relativedelta import relativedelta
from frappe.contacts.address_and_contact import load_address_and_contact
from rigpl_erpnext.utils.rigpl_perm import check_role, create_new_user_perm, delete_permission, \
    get_employees_allowed_ids, get_permission, get_user_roles
from rigpl_erpnext.utils.other_utils import validate_pan, validate_aadhaar
from rigpl_erpnext.hr_rigpl.utils.hr_utils import BYPASS_LABEL, block_message, get_active_duplicates, \
    get_branch_country, is_aadhaar_applicable
from rohit_common.utils.rohit_common_utils import fn_check_digit
from rohit_common.utils.email_utils import comma_email_validations


def onload(doc, method):
    load_address_and_contact(doc)


def validate(doc, method):
    # Validation for Age of Employee should be Greater than 18 years at the time of Joining.
    if doc.holiday_list:
        is_base_list = frappe.get_value("Holiday List", doc.holiday_list, "is_base_list")
        if is_base_list != 1:
            frappe.throw(f"{doc.holiday_list} is not a Base List Select a Base List in {doc.name}")
    if doc.company_email:
        cmp_validated_email = comma_email_validations(doc.company_email)
        multi_emails = split_emails(cmp_validated_email)
        if len(multi_emails) > 1:
            frappe.throw(f"Only 1 Email is allowed in Company Email field {doc.company_email} entered Rejected")
    if doc.personal_email:
        doc.personal_email = comma_email_validations(doc.personal_email)
    dob = getdate(doc.date_of_birth)
    doj = getdate(doc.date_of_joining)
    if relativedelta(doj, dob).years < 18:
        frappe.msgprint("Not Allowed to Create Employees under 18 years of Age", raise_exception=1)
    if doc.relieving_date:
        if doc.status != "Left":
            frappe.msgprint("Status has to be 'LEFT' as the Relieving Date is populated", raise_exception=1)
    if doc.status == "Left":
        doc.department = "All Departments"

    if not doc.department:
        frappe.throw("Department is Mandatory for Employee {}".format(doc.name))

    doc.employee_number = doc.name
    doc.employee = doc.name
    check_bypass_change(doc)
    validate_aadhaar_rules(doc)
    if doc.pan_number:
        validate_pan(doc.pan_number)


def check_bypass_change(doc):
    changed = cint(doc.get("allow_duplicate_aadhaar")) == 1 if doc.is_new() else \
        doc.has_value_changed("allow_duplicate_aadhaar")
    if changed and "System Manager" not in frappe.get_roles():
        frappe.throw("Only a System Manager can change {} in {}".format(BYPASS_LABEL, doc.name))


def validate_aadhaar_rules(doc):
    """Aadhaar is mandatory, valid and unique among Active Employees when the Country of the Branch
    has Aadhaar Applicable"""
    country = get_branch_country(doc.branch)
    if not country:
        message = "Set the Country in {} first. The Aadhaar rules of an Employee depend on it.".format(
            frappe.get_desk_link("Branch", doc.branch))
        if doc.is_new():
            frappe.throw(message)
        frappe.msgprint(message, indicator="orange")
        return
    if not is_aadhaar_applicable(country):
        return
    if not doc.aadhaar_number:
        frappe.throw("Aadhaar Number is mandatory for Employees of Branch {} in {}".format(doc.branch, country))
    validate_aadhaar(doc.aadhaar_number)
    if doc.status != "Active" or cint(doc.get("allow_duplicate_aadhaar")) == 1:
        return
    others = [name for name in get_active_duplicates([doc.aadhaar_number]).get(doc.aadhaar_number, [])
        if name != doc.name]
    if others:
        frappe.msgprint(block_message(doc.name, others, "any Attendance or Salary Slip"),
            title="Duplicate Aadhaar", indicator="orange")


def on_update(doc, method):
    allowed_ids = []
    allowed_ids = get_employees_allowed_ids(doc.employee)
    for user in allowed_ids:
        role_list = get_user_roles(user)
        role_in_settings, apply_to_all_doctypes, applicable_for = \
            check_role(role_list, "Employee", apply_to_all_doctypes="None")
        if role_in_settings == 1:
            create_new_user_perm(allow="Employee", for_value=doc.name, user=user,
                                 apply_to_all_doctypes=apply_to_all_doctypes, applicable_for=applicable_for)
    emp_perm_list = get_permission(allow="Employee", for_value=doc.name)
    for perm in emp_perm_list:
        if perm[3] not in allowed_ids:
            delete_permission(perm[0])


def autoname(doc, method):
    doj = getdate(doc.date_of_joining)
    series_id = frappe.db.sql("""SELECT current FROM `tabSeries` WHERE name = %s""", doc.naming_series, as_list=1)
    series_id = str(series_id[0][0])
    # Generate employee number on the following logic
    # Employee Number would be YYYYMMDDXXXXC, where:
    # YYYYMMDD = Date of Joining in YYYYMMDD format
    # XXXX = Serial Number of the employee from the ID this is NUMBERIC only
    # C= Check DIGIT
    if doc.date_of_joining:
        doj = str(doj.year) + str(doj.month).zfill(2)
        code = doj + series_id
        check = fn_check_digit(code)
        code = code + str(check)
    doc.name = code
