#  Copyright (c) 2021. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt

# -*- coding: utf-8 -*-

app_name = "rigpl_erpnext"
app_title = "Rohit ERPNext Extensions"
app_publisher = "Rohit Industries Group Private Limited"
app_description = "Rohit ERPNext Extensions"
app_icon = "icon-paper-clip"
app_color = "#007AFF"
app_email = "aditya@rigpl.com"
app_url = "https://github.com/adityaduggal/rigpl-erpnext"
app_version = "0.0.1"
hide_in_installer = True
# rohit_common defines doctypes (e.g. State) that rigpl customizations link to
required_apps = ["erpnext", "rohit_common"]

# Fixtures help https://frappeframework.com/docs/v13/user/en/python-api/hooks#fixtures
fixtures = []


# override_whitelisted_methods = {
# Below mentod would also take into account the search fields mentioned in the Customize form view
#    "erpnext.accounts.doctype.pricing_rule.pricing_rule.apply_pricing_rule":
#    "rigpl_erpnext.accounts_rigpl.validations.pricing_rule.apply_pricing_rule"
# }

# controller_context = {
#    'Item': 'rigpl_erpnext.templates.generators.item'
# }

# website_item = {
#    'get_item_meta': get_item_meta,
#    'get_item_attribute_data': get_item_attribute_data
# }

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/css/rigpl.css"
app_include_js = ["/assets/rigpl_erpnext/js/report_formatter.js"]

# include js, css files in header of web template
# web_include_css = "/assets/rigpl_erpnext/css/rigpl_erpnext.css"
# web_include_js = "/assets/rigpl_erpnext/js/rigpl_erpnext.js"

# Home Pages
# ----------
website_generators = ["Carrier Tracking"]
# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#   "Role": "home_page"
# }

# When a Portal Page is rendered, a dictionary is built with all of the possible variables that the page might
# need to render. This dict is also known as context. You can use these hooks to add or modify values in this dict.

# website_context = {
#    "favicon": "/assets/app/image/favicon.png"
# }

update_website_context = ["rigpl_erpnext.website_rigpl.item_page.update_website_context"]

# The guest API and the place order message show the capped stock label, not the real quantity (#127)
override_whitelisted_methods = {
    "erpnext.e_commerce.shopping_cart.product_info.get_product_info_for_website": "rigpl_erpnext.website_rigpl.product_info.get_product_info_for_website",
    "erpnext.e_commerce.shopping_cart.cart.place_order": "rigpl_erpnext.website_rigpl.cart.place_order",
    # Category pages show their sub-categories in sales order (#103)
    "erpnext.e_commerce.api.get_product_filter_data": "rigpl_erpnext.website_rigpl.product_listing.get_product_filter_data",
}

jenv = {"methods": ["rigpl_variant_table:rigpl_erpnext.website_rigpl.catalog.get_variant_table"]}

# You can use the update_website_context hook for more complex scenarios as it allows you to manipulate the
# context dict in a python method. The method is called with one argument, which is the context dict

# Installation
# ------------

# before_install = "rigpl_erpnext.install.before_install"
# after_install = "rigpl_erpnext.setup.after_install"
before_migrate = [
    "rigpl_erpnext.patches.v13.fix_long_item_names.execute",
    "rigpl_erpnext.patches.v13.fix_duplicate_renamed_doctype_tables.execute",
]

# v13 only: backport of v14 pricing rule "Has Priority". Remove at the v14 upgrade.
before_request = ["rigpl_erpnext.overrides.pricing_rule_utils.apply_overrides"]
before_job = ["rigpl_erpnext.overrides.pricing_rule_utils.apply_overrides"]
after_migrate = [
    "rigpl_erpnext.website_rigpl.website_data.importer.notify_pending_website_import",
    "rigpl_erpnext.utils.role_permission_policy.enforce_role_permission_policy",
]

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "rigpl_erpnext.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#   "Event": "frappe.core.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#   "Event": "frappe.core.doctype.event.event.has_permission",
# }

# Javascripts for Standard Documents to Override Forms Script
# -----------
doctype_js = {
    "Bank Account": "public/js/bank_account.js",
    "Item": "public/js/stock/item.js",
    "Leave Allocation": "public/js/hr/leave_allocation.js",
    "ToDo": "public/js/todo.js",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Account": {"validate": "rigpl_erpnext.rigpl_erpnext.validations.account.validate"},
    "Address": {"on_update": "rigpl_erpnext.rigpl_erpnext.validations.lead_share.address_on_update"},
    "Attendance": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.attendance.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.attendance.on_update",
        "update_after_submit": "rigpl_erpnext.rigpl_erpnext.validations.attendance.on_update",
    },
    "Bank Account": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.bank_account.validate",
        "autoname": "rigpl_erpnext.rigpl_erpnext.validations.bank_account.autoname",
    },
    "Blog Post": {
        "on_update": "rigpl_erpnext.website_rigpl.website_data.importer.clear_cache_on_blog_change",
        "on_trash": "rigpl_erpnext.website_rigpl.website_data.importer.clear_cache_on_blog_change",
    },
    "Communication": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.communication.validate",
        "after_insert": "rigpl_erpnext.rigpl_erpnext.validations.communication.after_insert",
    },
    "Customer": {
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.customer.on_update",
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.customer.validate",
    },
    "Delivery Note": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.delivery_note.on_cancel",
    },
    "Department": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.department.validate"
    },
    "Employee": {
        "onload": "rigpl_erpnext.rigpl_erpnext.validations.employee.onload",
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.employee.validate",
        "autoname": "rigpl_erpnext.rigpl_erpnext.validations.employee.autoname",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.employee.on_update",
    },
    "Expense Claim": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.expense_claim.validate"
    },
    "Holiday List": {
        "validate": "rigpl_erpnext.hr_rigpl.validations.holiday_list.validate"
    },
    "Item": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.item.validate",
        "autoname": "rigpl_erpnext.rigpl_erpnext.validations.item.autoname",
        "on_update": "rigpl_erpnext.website_rigpl.item_sync.on_item_update",
    },
    "Item Group": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.item_group.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.item_group.on_update",
    },
    "Item Price": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.item_price.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.item_price.on_update",
    },
    "Lead": {
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.lead.on_update",
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.lead.validate",
    },
    "Leave Allocation": {
        "validate": "rigpl_erpnext.hr_rigpl.validations.leave_allocation.validate"
    },
    "Leave Application": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.leave_application.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.leave_application.on_submit",
    },
    "Leave Policy": {
        "validate": "rigpl_erpnext.hr_rigpl.validations.leave_policy.validate"
    },
    "Opportunity": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.opportunity.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.lead_share.opportunity_on_update",
    },
    "Payment Entry": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.payment_entry.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.payment_entry.on_submit",
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
    },
    "Purchase Invoice": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.purchase_invoice.validate"
    },
    "Purchase Receipt": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.purchase_receipt.on_cancel",
    },
    "Quotation": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.quotation.validate",
        "on_update": "rigpl_erpnext.rigpl_erpnext.validations.lead_share.quotation_on_update",
    },
    "Salary Component": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_component.validate"
    },
    "Salary Slip": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_slip.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.salary_slip.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.salary_slip.on_cancel",
    },
    "Salary Structure": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_structure.validate"
    },
    "Salary Structure Assignment": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.salary_structure_assignment.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.salary_structure_assignment.on_submit",
    },
    "Sales Invoice": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.on_submit",
        "on_cancel": "rigpl_erpnext.rigpl_erpnext.validations.sales_invoice.on_cancel",
    },
    "Sales Person": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.sales_person.validate"
    },
    "Sales Order": {
        "validate": "rigpl_erpnext.selling_rigpl.validations.sales_order.validate",
        "on_submit": "rigpl_erpnext.selling_rigpl.validations.sales_order.on_submit",
        "on_cancel": "rigpl_erpnext.selling_rigpl.validations.sales_order.on_cancel",
    },
    "Stock Entry": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.stock_entry.validate",
        "on_submit": "rigpl_erpnext.rigpl_erpnext.validations.stock_entry.on_submit",
    },
    "Stock Reconciliation": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.stock_reconciliation.validate"
    },
    "Supplier": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.supplier.validate"
    },
    "ToDo": {"validate": "rigpl_erpnext.rigpl_erpnext.validations.todo.validate"},
    "Warehouse": {
        "validate": "rigpl_erpnext.rigpl_erpnext.validations.warehouse.validate"
    },
    "Web Page": {"validate": "rigpl_erpnext.website_rigpl.route_sync.web_page_validate"},
    "Website Item": {
        "validate": "rigpl_erpnext.website_rigpl.route_sync.website_item_validate",
        "on_update": "rigpl_erpnext.website_rigpl.route_sync.website_item_on_update",
    },
    "Workstation": {
        "validate": "rigpl_erpnext.manufacturing_rigpl.validations.workstation.validate"
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "*/30 * * * *": [
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.manufacturing_pipeline.enqueue_pipeline"
            # Process Sheets and Job Cards, one copy at a time (#145)
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
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.customer_rating.enqueue_job",
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_reorder.enqueue_rol_job",
            "rigpl_erpnext.website_rigpl.sales_rank.enqueue_sales_rank",
            "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_calculate_lead_times.enqueue_job"
            # Runs on 1st Quarter End Jan, Apr, Jul, Oct at 3:15 AM
        ],
    },
    "daily_long": [
        "rigpl_erpnext.rigpl_erpnext.doctype.carrier_tracking.common.unpublish_old_ctracks",
        "rigpl_erpnext.utils.role_permission_policy.enforce_role_permission_policy",
    ],
    "hourly_long": [
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.user_permission_sync.execute",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.communication.create_follow_up_todos",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update.send_bulk_tracks",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.shipment_data_update.get_all_ship_data",
        "rigpl_erpnext.rigpl_erpnext.scheduled_tasks.automate_docshare.execute",
    ],
}

# Testing
# -------

# before_tests = "rigpl_erpnext.install.before_tests"
