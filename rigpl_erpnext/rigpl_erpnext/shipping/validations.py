"""Carrier Tracking checks that do not call a carrier (moved from the old jobs module, #168)."""
import math
from typing import Optional, Tuple

import frappe
from erpnext import get_default_currency
from erpnext.setup.utils import get_exchange_rate
from frappe.utils import flt, fmt_money


def cost_over_limit(shipment_cost, amount, max_percent_of_invoice_value) -> bool:
    """True when the shipment cost is more than the allowed percent of the invoice value."""
    if max_percent_of_invoice_value is None or shipment_cost is None or flt(amount) <= 0:
        return False
    return flt(shipment_cost) / flt(amount) * 100 > flt(max_percent_of_invoice_value)


def courier_charges_validation(ct_doc, max_percent_of_invoice_value, backend: bool = False) -> int:
    """1 when the courier cost is over the allowed percent of the invoice value and the
    courier is not charged enough. On a SOLD Sales Invoice this stops the save, unless
    `bypass_courier_charged_check` is set or `backend` is true."""
    if max_percent_of_invoice_value is None:
        return 0
    rate = invoice_rate(ct_doc)
    amount, cost = company_currency_values(ct_doc, rate)
    if flt(ct_doc.shipment_cost) and not cost:
        frappe.throw(f"No exchange rate for {ct_doc.shipment_cost_currency}. Add a Currency Exchange record.",
                     title="Exchange Rate Needed")
    if not cost_over_limit(cost, amount, max_percent_of_invoice_value):
        return 0
    sold_invoice = ct_doc.purpose == "SOLD" and ct_doc.document == "Sales Invoice"
    if not sold_invoice:
        if ct_doc.purpose != "SOLD" and ct_doc.document != "Sales Invoice":
            frappe.msgprint(f"Permissible Courier Cost is High. Make sure you charge courier for Minimum Amount of "
                            f"{flt(cost, 2)}", title="Warning From Admin")
        return 0
    if flt(ct_doc.courier_charged) < cost and not ct_doc.bypass_courier_charged_check:
        if not backend:
            frappe.throw(low_charge_message(ct_doc, cost, rate), title="Courier Charges Too Low")
        return 1
    return 0


def low_charge_message(ct_doc, cost: float, rate: Optional[float]) -> str:
    """Which invoice and account were checked, and the courier charge that passes the check.
    `cost` is in the company currency, `rate` is the conversion rate of the invoice."""
    company = get_default_currency()
    account = frappe.get_cached_value("Transporters", ct_doc.carrier_name, "invoice_courier_charges_account")
    account_link = frappe.get_desk_link("Account", account) if account else "<b>not set</b>"
    needed = fmt_money(cost, 2, company)
    if ct_doc.currency and ct_doc.currency != company and flt(rate):
        # rounded up, so the charge is never below the cost
        foreign = math.ceil(round(cost / flt(rate) * 100, 6)) / 100
        needed = f"{fmt_money(foreign, 2, ct_doc.currency)} ({needed} at rate {flt(rate)})"
    return "<br>".join((
        f"{frappe.get_desk_link('Sales Invoice', ct_doc.document_name)} does not charge enough courier for "
        f"{ct_doc.name}.",
        f"Account checked: {account_link} (Invoice Courier Charges Account in "
        f"{frappe.get_desk_link('Transporters', ct_doc.carrier_name)})",
        f"Charged now: {fmt_money(flt(ct_doc.courier_charged), 2, company)}",
        f"Charge at least: <b>{needed}</b>",
        "Or check <b>Bypass Courier Charged Check</b> on the tracking, if your permissions allow it.",
    ))


def company_currency_values(ct, conversion_rate: Optional[float] = None, rates: dict = None) -> Tuple[float, float]:
    """(invoice amount, shipment cost) of a Carrier Tracking in the company currency (#246).
    `conversion_rate` is the rate of the invoice for `ct.currency`. An empty currency is the
    company currency. `rates` keeps the other exchange rates between calls. A value with no
    exchange rate is 0."""
    rates = {} if rates is None else rates

    def convert(value, currency) -> float:
        if not flt(value) or not currency or currency == get_default_currency():
            return flt(value)
        if currency == ct.get("currency") and flt(conversion_rate):
            return flt(value) * flt(conversion_rate)
        if currency not in rates:
            rates[currency] = flt(get_exchange_rate(currency, get_default_currency()))
        return flt(value) * rates[currency]

    return convert(ct.get("amount"), ct.get("currency")), \
        convert(ct.get("shipment_cost"), ct.get("shipment_cost_currency"))


def invoice_rate(ct_doc) -> Optional[float]:
    if ct_doc.document != "Sales Invoice" or not ct_doc.document_name:
        return None
    return frappe.db.get_value("Sales Invoice", ct_doc.document_name, "conversion_rate")
