# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import re
import frappe
import phonenumbers
from frappe.utils import cint, getdate, split_emails, validate_phone_number
from dateutil.relativedelta import relativedelta
from frappe.contacts.address_and_contact import load_address_and_contact
from rigpl_erpnext.utils.rigpl_perm import check_role, create_new_user_perm, delete_permission, \
    get_employees_allowed_ids, get_permission, get_user_roles
from rigpl_erpnext.utils.other_utils import validate_pan, validate_aadhaar
from rigpl_erpnext.hr_rigpl.utils.hr_utils import BYPASS_LABEL, block_message, get_active_duplicates, \
    get_branch_country, is_aadhaar_applicable
from rohit_common.utils.rohit_common_utils import fn_check_digit
from rohit_common.utils.email_utils import comma_email_validations

PHONE_FIELDS = ("cell_number", "emergency_phone_number")
PHONE_WORDS = re.compile(r"\b(mob(ile)?|ph(one)?|tel)\b\.?:?", re.IGNORECASE)


def onload(doc, method):
    load_address_and_contact(doc)


def split_phone_field(text, region="IN"):
    """Returns ([phone numbers as typed], the other text) of a phone field"""
    numbers, rest, last = [], [], 0
    for match in phonenumbers.PhoneNumberMatcher(text, region):
        numbers.append(match.raw_string.strip("()"))
        rest.append(text[last:match.start])
        last = match.end
    rest.append(text[last:])
    rest_text = PHONE_WORDS.sub(" ", " ".join(rest))
    return numbers, re.sub(r"[\s,/&()\-:]+", " ", rest_text).strip()


def get_phone_region(doc):
    country = get_branch_country(doc.branch)
    code = frappe.get_cached_value("Country", country, "code") if country else None
    return (code or "IN").upper()


def fix_phone_fields(doc):
    """v13 allows one phone number in Mobile and Emergency Phone. The first number stays. The other
    Mobile numbers go to the Contact of the Employee, the rest to a Comment (see save_moved_phones)"""
    doc.flags.extra_mobiles, doc.flags.phone_notes = [], []
    for field in PHONE_FIELDS:
        value = (doc.get(field) or "").strip()
        if not value or validate_phone_number(value):
            continue
        numbers, rest = split_phone_field(value, get_phone_region(doc))
        label = doc.meta.get_label(field)
        doc.set(field, numbers[0] if numbers else "")
        if field == "cell_number":
            doc.flags.extra_mobiles += numbers[1:]
        elif numbers[1:]:
            doc.flags.phone_notes.append("Other {} numbers: {}".format(label, ", ".join(numbers[1:])))
        if rest and field == "emergency_phone_number" and not doc.person_to_be_contacted:
            doc.person_to_be_contacted = rest
        elif rest:
            doc.flags.phone_notes.append("Text removed from {}: {}".format(label, rest))
        frappe.msgprint("{} allows one phone number. Kept {}. The other Mobile numbers go to the Contact of the "
            "Employee in a minute, the rest to a Comment.".format(label, doc.get(field) or "none"), indicator="orange")


def save_moved_phones(doc):
    extra_mobiles, notes = doc.flags.extra_mobiles or [], list(doc.flags.phone_notes or [])
    doc.flags.extra_mobiles = doc.flags.phone_notes = None
    if extra_mobiles:
        # A new Contact commits in ERPNext's after_insert (call_log.link_existing_conversations), so it
        # is saved in a job after the Employee is committed
        frappe.enqueue("rigpl_erpnext.rigpl_erpnext.validations.employee.add_mobiles_to_contact",
            employee=doc.name, mobiles=extra_mobiles, enqueue_after_commit=True)
    if notes:
        doc.add_comment("Comment", "<br>".join(notes))


def add_mobiles_to_contact(employee, mobiles):
    """Adds the mobiles to the Contact linked to the Employee, or to a new one. If the Contact does
    not save (a Contact with 2 mobiles fails the v13 phone check), the numbers go to a Comment."""
    doc = frappe.get_doc("Employee", employee)
    name = frappe.db.get_value("Dynamic Link", {"link_doctype": "Employee", "link_name": doc.name,
        "parenttype": "Contact"}, "parent")
    contact = frappe.get_doc("Contact", name) if name else frappe.get_doc({"doctype": "Contact",
        "first_name": doc.employee_name or doc.first_name,
        "links": [{"link_doctype": "Employee", "link_name": doc.name}]})
    known = {re.sub(r"\D", "", row.phone or "")[-10:] for row in contact.get("phone_nos") or []}
    country = get_branch_country(doc.branch)
    new = [num for num in mobiles if re.sub(r"\D", "", num)[-10:] not in known]
    if not new:
        return
    for num in new:
        contact.append("phone_nos", {"phone": num, "country": country})
    contact.flags.ignore_permissions = True
    frappe.db.savepoint("employee_contact")
    try:
        contact.save()
    except frappe.ValidationError:
        frappe.db.rollback(save_point="employee_contact")
        frappe.clear_last_message()
        doc.add_comment("Comment", "Other Mobile numbers: {}".format(", ".join(new)))


def validate(doc, method):
    fix_phone_fields(doc)
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
    save_moved_phones(doc)
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
