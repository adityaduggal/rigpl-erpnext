import frappe

def run_unwanted_patches():
    """
    Marks the two specified failing patches as run in Patch Log.
    """
    if not frappe.db.exists("Patch Log", {"patch": "frappe.patches.v16.skip_final_patches"}):
        
        # 1. Skip V13 patch failing due to Query Builder issues (timestampdiff)
        skip_update_response_by_variance()
        
        # 2. Skip V14 patch failing due to MandatoryError on Workspace child table
        skip_update_workspace2()
        
        running_unwanted_patches_log()

def skip_update_response_by_variance():
    """Skip erpnext.patches.v13_0.update_response_by_variance."""
    frappe.get_doc({
        'doctype': 'Patch Log',
        'patch': 'erpnext.patches.v13_0.update_response_by_variance',
    }).insert(ignore_permissions=True)
    frappe.db.commit()

def skip_update_workspace2():
    """Skip frappe.patches.v14_0.update_workspace2 # 06.06.2023."""
    # The actual patch name includes the date/comment
    frappe.get_doc({
        'doctype': 'Patch Log',
        'patch': 'frappe.patches.v14_0.update_workspace2 # 06.06.2023',
    }).insert(ignore_permissions=True)
    frappe.db.commit()

def running_unwanted_patches_log():
    """Log the execution of this skipping routine to prevent re-execution."""
    frappe.get_doc({
        'doctype': 'Patch Log',
        'patch': 'frappe.patches.v16.skip_final_patches',
    }).insert(ignore_permissions=True)
    frappe.db.commit()