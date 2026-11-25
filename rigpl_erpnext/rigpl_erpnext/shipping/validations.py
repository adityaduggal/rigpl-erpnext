"""Carrier Tracking checks that do not call a carrier (moved from the old jobs module, #168)."""
import math
from typing import Dict, Iterable, Optional, Tuple

import frappe
from erpnext import get_default_currency
from erpnext.setup.utils import get_exchange_rate
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt, fmt_money

from .accounts import NONE
from .registry import provider_classes, transporter_api
from ...utils.item_attribute_utils import chunks


def cost_over_limit(shipment_cost, amount, max_percent_of_invoice_value) -> bool:
    """True when the shipment cost is more than the allowed percent of the invoice value."""
    if max_percent_of_invoice_value is None or shipment_cost is None or flt(amount) <= 0:
        return False
    return flt(shipment_cost) / flt(amount) * 100 > flt(max_percent_of_invoice_value)


def courier_charges_validation(ct_doc, max_percent_of_invoice_value, backend: bool = False) -> int:
    """1 when the courier charged on a SOLD Sales Invoice is below the shipment cost less the
    allowed percent of the invoice value (#248). This stops the save, unless
    `bypass_courier_charged_check` is set or `backend` is true. Other documents get a warning.
    A transporter with no source for the cost is not checked."""
    if max_percent_of_invoice_value is None or not cost_is_known(ct_doc.carrier_name):
        return 0
    rate = invoice_rate(ct_doc)
    amount, cost = company_currency_values(ct_doc, rate)
    if flt(ct_doc.shipment_cost) and not cost:
        frappe.throw(f"No exchange rate for {ct_doc.shipment_cost_currency}. Add a Currency Exchange record.",
                     title="Exchange Rate Needed")
    allowed = amount * flt(max_percent_of_invoice_value) / 100
    required = flt(cost - allowed, 2)
    if required <= 0:
        return 0
    sold_invoice = ct_doc.purpose == "SOLD" and ct_doc.document == "Sales Invoice"
    if not sold_invoice:
        if ct_doc.purpose != "SOLD" and ct_doc.document != "Sales Invoice":
            frappe.msgprint(f"Permissible Courier Cost is High. Make sure you charge courier for Minimum Amount of "
                            f"{fmt_money(round_up_charge(required), 2, get_default_currency())}",
                            title="Warning From Admin")
        return 0
    if flt(ct_doc.courier_charged, 2) < required and not ct_doc.bypass_courier_charged_check:
        if not backend:
            frappe.throw(low_charge_message(ct_doc, cost, required, max_percent_of_invoice_value, rate),
                         title="Courier Charges Too Low")
        return 1
    return 0


def courier_charges(invoice_accounts: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], float]:
    """{(Sales Invoice, account): courier charged in the company currency}, from the item rows and the
    tax rows with that account (#249). A pair with no row is not in the result."""
    pairs = {(invoice, account) for invoice, account in invoice_accounts if invoice and account}
    accounts = list({account for _, account in pairs})
    sources = (("Sales Invoice Item", "income_account", "base_amount"),
               ("Sales Taxes and Charges", "account_head", "base_tax_amount_after_discount_amount"))
    charges = {}
    for invoices in chunks(invoice for invoice, _ in pairs):
        for doctype, account_field, amount_field in sources:
            table = frappe.qb.DocType(doctype)
            rows = (
                frappe.qb.from_(table)
                .select(table.parent, table[account_field], Sum(table[amount_field]))
                .where(table.parenttype == "Sales Invoice")
                .where(table.parent.isin(invoices))
                .where(table[account_field].isin(accounts))
                .groupby(table.parent, table[account_field])
            ).run()
            for invoice, account, amount in rows:
                if (invoice, account) in pairs:
                    charges[(invoice, account)] = charges.get((invoice, account), 0) + flt(amount)
    return charges


def cost_is_known(transporter: str) -> bool:
    """True when the system gets the cost: from the Transporter quote, or from a rate API."""
    if cint(frappe.get_cached_value("Transporters", transporter, "calculate_cost_from_quote")):
        return True
    provider, api_mode = transporter_api(transporter)
    provider_class = provider_classes().get(provider)
    return api_mode != NONE and bool(provider_class) and "rate" in provider_class.capabilities


def low_charge_message(ct_doc, cost: float, required: float, max_percent: float, rate: Optional[float]) -> str:
    """Which invoice and account were checked, and the courier charge that passes the check.
    `cost` and `required` are in the company currency, `rate` is the conversion rate of the invoice."""
    company = get_default_currency()
    account = frappe.get_cached_value("Transporters", ct_doc.carrier_name, "invoice_courier_charges_account")
    account_link = frappe.get_desk_link("Account", account) if account else "<b>not set</b>"
    if ct_doc.currency and ct_doc.currency != company and flt(rate):
        foreign = round_up_charge(required / flt(rate))
        needed = (f"<b>{fmt_money(foreign, 2, ct_doc.currency)}</b> "
                  f"({fmt_money(foreign * flt(rate), 2, company)} at rate {flt(rate)})")
    else:
        needed = f"<b>{fmt_money(round_up_charge(required), 2, company)}</b>"
    return "<br>".join((
        f"{frappe.get_desk_link('Sales Invoice', ct_doc.document_name)} does not charge enough courier for "
        f"{ct_doc.name}.",
        f"Account checked: {account_link} (Invoice Courier Charges Account in "
        f"{frappe.get_desk_link('Transporters', ct_doc.carrier_name)})",
        f"Shipment cost: {fmt_money(cost, 2, company)}. Allowed without charge: {flt(max_percent)}% of the "
        "invoice value.",
        f"Charged now: {fmt_money(flt(ct_doc.courier_charged), 2, company)}",
        f"Charge at least: {needed}",
        "Or check <b>Bypass Courier Charged Check</b> on the tracking, if your permissions allow it.",
    ))


def round_up_charge(value: float) -> int:
    """Rounds up by a power of 10 that is at most 1% of the value, and at least 1."""
    step = 10 ** max(math.floor(math.log10(value / 100)), 0)
    return math.ceil(round(value / step, 6)) * step


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
