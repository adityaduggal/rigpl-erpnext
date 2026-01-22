# -*- coding: utf-8 -*-
"""
Patch to migrate Employee Advance data to Employee Advance RIGPL

This patch copies all existing Employee Advance records (RIGPL custom format)
to the new Employee Advance RIGPL table, and updates child table references.
"""

import frappe


def execute():
    # Check if source table has data
    count = frappe.db.sql("SELECT COUNT(*) FROM `tabEmployee Advance`")[0][0]
    if not count:
        print("No Employee Advance records to migrate")
        return
    
    # Check if destination DocType exists
    if not frappe.db.exists("DocType", "Employee Advance RIGPL"):
        print("DocType Employee Advance RIGPL not found. Run bench migrate first.")
        return
    
    print(f"Migrating {count} Employee Advance records to Employee Advance RIGPL...")
    
    # Columns that exist in Employee Advance RIGPL (from our custom doctype)
    # These are the standard frappe fields + our custom fields
    target_columns = [
        "name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
        "posting_date", "total_loan", "debit_account", "deduction_type", 
        "credit_account", "amended_from"
    ]
    
    # Build column list for INSERT
    cols = ", ".join([f"`{c}`" for c in target_columns])
    
    # Copy data with explicit columns
    frappe.db.sql(f"""
        INSERT INTO `tabEmployee Advance RIGPL` ({cols})
        SELECT {cols} FROM `tabEmployee Advance`
    """)
    
    # Update child table parenttype
    frappe.db.sql("""
        UPDATE `tabEmployee Loan Detail` 
        SET parenttype = 'Employee Advance RIGPL' 
        WHERE parenttype = 'Employee Advance'
    """)
    
    frappe.db.commit()
    
    print(f"Successfully migrated {count} records to Employee Advance RIGPL")
    print("Child table Employee Loan Detail parenttype updated")
