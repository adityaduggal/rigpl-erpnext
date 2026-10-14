import frappe


def execute():
    """
    Commit daf349b removed the Homepage Section Content doctype but left the
    Homepage Section custom field that links to it. Removes both from existing sites.
    """
    frappe.delete_doc_if_exists("Custom Field", "Homepage Section-section_content")
    frappe.delete_doc_if_exists("DocType", "Homepage Section Content")
