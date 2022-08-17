import frappe


def execute():
    """
    This code should be executed manually only since it cancels old Loans
    """
    old_loans = frappe.db.sql(
        """SELECT name FROM `tabLoan` WHERE docstatus = 1 ORDER BY name""", as_dict=1)
    for loan in old_loans:
        frappe.db.set_value("Loan", loan.name, "docstatus", 2)
        print(f"Setting Docstatus = Cancelled for Loan {loan.name}")
