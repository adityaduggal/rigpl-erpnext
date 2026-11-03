#  Copyright (c) 2026. Rohit Industries Group Private Limited and Contributors.
#  For license information, please see license.txt
"""
One API account of a shipping provider (#168). Transporters link to it with
`shipping_provider_account`, and `api_mode` says what the code may do with it.
The provider adapters in `rigpl_erpnext/shipping/providers/` read it.
"""
from frappe.model.document import Document


class ShippingProviderAccount(Document):
    pass
