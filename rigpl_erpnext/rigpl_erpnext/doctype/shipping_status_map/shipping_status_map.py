#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
Maps the tracking codes of a carrier to the statuses of Carrier Tracking (#168).
The name is fixed by provider, match type and code, so one code has one row.
"""
from frappe.model.document import Document

from rigpl_erpnext.rigpl_erpnext.shipping.status_map import clear_status_map_cache, rule_name


class ShippingStatusMap(Document):
    def autoname(self):
        self.carrier_code = (self.carrier_code or "").strip()
        self.name = rule_name(self.provider, self.match_on, self.carrier_code)

    def on_update(self):
        clear_status_map_cache()

    def on_trash(self):
        clear_status_map_cache()
