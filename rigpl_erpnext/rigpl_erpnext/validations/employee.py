# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from rigpl_erpnext.utils.rigpl_perm import *
from frappe.utils import getdate, split_emails
from dateutil.relativedelta import relativedelta
from frappe.contacts.address_and_contact import load_address_and_contact
from rigpl_erpnext.utils.other_utils import validate_pan, validate_aadhaar
from rohit_common.utils.rohit_common_utils import fn_check_digit
from rohit_common.rohit_common.integrations.email_verification.email_verification \
    import full_email_validation


def onload(doc, method):
    load_address_and_contact(doc)


def validate(doc, method):
    # Validation for Age of Employee should be Greater than 18 years at the time of Joining.
    if doc.holiday_list:
        is_base_list = frappe.get_value("Holiday List", doc.holiday_list, "is_base_list")
        if is_base_list != 1:
            frappe.throw(f"{doc.holiday_list} is not a Base List Select a Base List in {doc.name}")
    if doc.company_email:
        cmp_validated_email = full_email_validation(doc.company_email)
        multi_emails = split_emails(cmp_validated_email)
        if len(multi_emails) > 1:
            frappe.throw(f"Only 1 Email is allowed in Company Email field {doc.company_email} entered Rejected")
    if doc.personal_email:
        doc.personal_email = full_email_validation(doc.personal_email)
    dob = getdate(doc.date_of_birth)
    doj = getdate(doc.date_of_joining)
    if relativedelta(doj, dob).years < 18:
        frappe.msgprint("Not Allowed to Create Employees under 18 years of Age", raise_exception=1)
    if doc.relieving_date:
        if doc.status != "Left":
            frappe.msgprint("Status has to be 'LEFT' as the Relieving Date is populated", raise_exception=1)
    if doc.status == "Left":
        doc.department = "All Departments"

    if doc.department == "":
        frappe.throw("Department is Mandatory for Employee {}".format(doc.name))

    doc.employee_number = doc.name
    doc.employee = doc.name
    if doc.aadhaar_number:
        validate_aadhaar(doc.aadhaar_number)
    if doc.pan_number:
        validate_pan(doc.pan_number)


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
    series_id = frappe.db.sql("""SELECT current FROM `tabSeries` WHERE name = '%s'""" % doc.naming_series, as_list=1)
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
