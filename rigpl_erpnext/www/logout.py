import frappe
from frappe import _

no_cache = True


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def on_request():
	"""Custom logout handler that accepts both GET and POST requests"""
	frappe.local.login_manager.logout()
	frappe.db.commit()
	frappe.respond_as_web_page(
		_("Logged Out"), _("You have been successfully logged out"), indicator_color="green"
	)
