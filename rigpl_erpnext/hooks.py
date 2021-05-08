#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .templates.generators.item.item import get_item_meta, get_item_attribute_data


app_name = "rigpl_erpnext"
app_title = "Rohit ERPNext Extensions"
app_publisher = "Rohit Industries Group Private Limited"
app_description = "Rohit ERPNext Extensions"
app_icon = "icon-paper-clip"
app_color = "#007AFF"
app_email = "aditya@rigpl.com"
app_url = "https://github.com/adityaduggal/custom_erpnext"
app_version = "0.0.1"
fixtures = ["Custom Script"]
hide_in_installer = True
home_page = "index"

controller_context = {
    'Item': 'rigpl_erpnext.templates.generators.item'
}

website_item = {
    'get_item_meta': get_item_meta,
    'get_item_attribute_data': get_item_attribute_data
}

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
website_generators = ["Carrier Tracking", "Item", "Item Group"]
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
    "Account": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.account.validate"
    },
    "Attendance": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.attendance.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.attendance.on_update",
        "update_after_submit": "rigpl_erpnext.rigpl_erpnext.validations.attendance.on_update"
    },
    "Bank Account": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.bank_account.validate",
        "autoname": "rigpl_erpnext.rigpl_erpnext.validations.bank_account.autoname"
    },
    "Communication": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.communication.validate"
    },
    "Customer": {
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.customer.on_update",
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.customer.validate"
    },
    "Delivery Note": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.on_cancel"
    },
    "Department": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.department.validate"
    },
    "Employee": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.employee.validate",
        "autoname": "rigpl_erpnext.rigpl_erpnext.validations.employee.autoname",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.employee.on_update",
    },
    "Expense Claim": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.expense_claim.validate"
    },
    "Holiday List": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.holiday_list.validate"
    },
    "Item": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.item.validate",
        "autoname": "rigpl_erpnext.rigpl_erpnext.validations.item.autoname"
    },
    "Item Group": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.item_group.validate"
    },
    "Item Price": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.item_price.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.item_price.on_update"
    },
    "Lead": {
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.lead.on_update",
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.lead.validate"
    },
    "Leave Application": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.leave_application.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.leave_application.on_submit"
    },
    "Opportunity": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.opportunity.validate"
    },
    "Payment Entry": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.payment_entry.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.payment_entry.on_submit"
    },
    "Price List": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.price_list.validate"
    },
    "Pricing Rule": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.pricing_rule.validate"
    },
    "Purchase Order": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.on_cancel",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.purchase_order.on_update"
    },
    "Purchase Invoice": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.purchase_invoice.validate"
    },
    "Purchase Receipt": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt.on_cancel"
    },
    "Quotation": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.quotation.validate"
    },
    "Salary Component": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_component.validate"
    },
    "Salary Slip": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_slip.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.salary_slip.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.salary_slip.on_cancel"
    },
    "Salary Structure": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_structure.validate"
    },
    "Salary Structure Assignment": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_structure_assignment.validate"
    },
    "Sales Invoice": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.on_cancel"
    },
    "Sales Person": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_person.validate"
    },
    "Sales Order": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_order.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.sales_order.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.sales_order.on_cancel"
    },
    "Stock Entry": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.stock_entry.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.stock_entry.on_submit"
    },
    "Stock Reconciliation": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.stock_reconciliation.validate"
    },
    "Supplier": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.supplier.validate"
    },
    "ToDo": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.todo.validate"
    },
    "Warehouse": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.warehouse.validate"
    },
    "Work Order": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.work_order.validate"
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "*/30 * * * *": [
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.indiamart.execute"
            # Runs Every 30 mins
        ],
        "10 2 * * *": [
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.variant_copy.enqueue_check_wrong_variants",
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.check_update_bin_values.enqueue_ex"
            # Runs everyday at 2:10 AM
        ],
        "10 3 * * 0": [
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.item_valuation_rate.enqueue_set_valuation_rate"
            # Runs weekly at 3:10 AM on Sunday
        ],
        "15 3 01 */3 *": [
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.customer_rating.execute"
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_reorder.enqueue_rol_job"
            # Runs on 1st Quarter End Jan, Apr, Jul, Oct at 3:15 AM
        ]
    },
    "all": [
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.default_permissions.create_defaults",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.update_job_card_status.update_rm_status_unmodified",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.create_new_job_cards.execute"
    ],
    "daily": [
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.permission_check.check_permission_exist"

    ],
    "hourly": [
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.communication.daily",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update.send_bulk_tracks",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update.enqueue_get_ship_data",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.automate_docshare.enqueue_docshare",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.update_job_card_status.execute",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.process_sheet_update.enqueue_process_sheet_update"
    ]
    # 	"monthly": [
    # 		"rigpl_erpnext.tasks.monthly"
    # 	]
}

# Testing
# -------

# before_tests = "rigpl_erpnext.install.before_tests"
