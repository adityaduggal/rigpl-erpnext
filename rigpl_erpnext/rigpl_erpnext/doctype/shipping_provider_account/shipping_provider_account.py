#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
One API account of a shipping provider (#168). Transporters link to it with
`shipping_provider_account`, and `api_mode` says what the code may do with it.
The provider adapters in `rigpl_erpnext/shipping/providers/` read it.
"""
from frappe.model.document import Document
from frappe.utils.password import remove_encrypted_password

# The fields that each adapter reads, besides account_name, provider, enabled and base_url.
# The form shows only these (depends_on in the JSON), and a save clears the others.
PROVIDER_FIELDS = {
    "FedEx": ("is_sandbox", "account_number", "client_id", "client_secret", "webhook_enabled", "webhook_secret"),
    "DTDC": ("customer_code", "api_key", "username", "password", "tracking_base_url", "serviceability_url",
             "webhook_enabled", "webhook_secret"),
    "Shipway": ("username", "password"),
}
OPTIONAL_FIELDS = tuple(dict.fromkeys(f for fields in PROVIDER_FIELDS.values() for f in fields))


class ShippingProviderAccount(Document):
    def validate(self):
        self.clear_unused_fields()

    def on_update(self):
        # An empty Password field keeps its stored secret, so the unused ones are deleted here
        for df in self.meta.get("fields", {"fieldtype": "Password"}):
            if df.fieldname in self.unused_fields():
                remove_encrypted_password(self.doctype, self.name, df.fieldname)

    def unused_fields(self):
        return [f for f in OPTIONAL_FIELDS if f not in PROVIDER_FIELDS.get(self.provider, ())]

    def clear_unused_fields(self):
        for fieldname in self.unused_fields():
            self.set(fieldname, 0 if self.meta.get_field(fieldname).fieldtype == "Check" else None)
