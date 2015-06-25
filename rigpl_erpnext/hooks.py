app_name = "rigpl_erpnext"
app_title = "Rohit ERPNext Extensions"
app_publisher = "Rohit Industries Ltd."
app_description = "Rohit ERPNext Extensions"
app_icon = "icon-paper-clip"
app_color = "#007AFF"
app_email = "aditya@rigpl.com"
app_url = "https://github.com/adityaduggal/custom_erpnext"
app_version = "0.0.1"

hide_in_installer = True

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/rigpl_erpnext/css/rigpl_erpnext.css"
# app_include_js = "/assets/rigpl_erpnext/js/rigpl_erpnext.js"

# include js, css files in header of web template
# web_include_css = "/assets/rigpl_erpnext/css/rigpl_erpnext.css"
# web_include_js = "/assets/rigpl_erpnext/js/rigpl_erpnext.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Installation
# ------------

# before_install = "rigpl_erpnext.install.before_install"
# after_install = "rigpl_erpnext.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "rigpl_erpnext.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.core.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.core.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"validate": "rigpl_erpnext.rigpl_erpnext.item.validate",
		"autoname": "rigpl_erpnext.rigpl_erpnext.item.autoname"
	},
	"Quality": {
		"autoname": "rigpl_erpnext.rigpl_erpnext.quality.autoname"
	},
	"Sales Invoice": {
		"validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.validate",
		"on_submit": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.on_submit",
		"on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.on_cancel"
	},
	"Sales Order": {
		"validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_order.validate",
		"on_submit": "rigpl_erpnext.rigpl_erpnext.validations.sales_order.on_submit",
		"on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.sales_order.on_cancel"
	},
	"Delivery Note": {
		"on_submit": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.on_submit",
		"on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.on_cancel"
	},
	"Stock Entry": {
		"validate": "rigpl_erpnext.rigpl_erpnext.validations.stock_entry.validate",
		"on_submit": "rigpl_erpnext.rigpl_erpnext.validations.stock_entry.validate"
	},
	"Lead": {
		"on_update": "rigpl_erpnext.rigpl_erpnext.validations.lead.on_update"
	},
	"Customer": {
		"on_update": "rigpl_erpnext.rigpl_erpnext.validations.customer.on_update"
	},
	"Attendance": {
		"validate": "rigpl_erpnext.rigpl_erpnext.validations.attendance.validate"
	},
	"Employee": {
		"validate": "rigpl_erpnext.rigpl_erpnext.validations.employee.validate"
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"rigpl_erpnext.tasks.all"
# 	],
# 	"daily": [
# 		"rigpl_erpnext.tasks.daily"
# 	],
# 	"hourly": [
# 		"rigpl_erpnext.tasks.hourly"
# 	],
# 	"weekly": [
# 		"rigpl_erpnext.tasks.weekly"
# 	]
# 	"monthly": [
# 		"rigpl_erpnext.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "rigpl_erpnext.install.before_tests"

