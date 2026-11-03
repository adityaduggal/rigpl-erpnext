"""
Who may open a Carrier Tracking web page, and for how long (#83).

- The route is a random token, so pages cannot be listed by name.
- A guest needs the signed link from the shipment email: HMAC-SHA256 over (name, exp) with
  a key made from the site encryption key. `sig` and `exp` come from the URL only.
- A logged-in user may open it when one of their Contacts is linked to the receiver, or
  when they can read the document in the desk.
- The page expires on the same rules as `tracking.unpublish_ctracks`.
"""
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional

import frappe
from frappe.utils import cint, get_datetime, get_url, now_datetime
from frappe.utils.password import get_encryption_key

from . import status as st
from .settings import ShippingSettings, get_shipping_settings

ROUTE_LENGTH = 20
SALT = b"rigpl-carrier-tracking-link"


def new_route() -> str:
    return frappe.generate_hash(length=ROUTE_LENGTH)


def needs_new_route(name: str, route: Optional[str]) -> bool:
    """True when the route is empty or still the old guessable `name.lower()`."""
    return not route or route == (name or "").lower()


def access_expires_on(doc, settings: Optional[ShippingSettings] = None) -> datetime:
    """The earlier of creation + published_ctrack_days and, once delivered,
    delivery + unpublish_after_delivery_days."""
    settings = settings or get_shipping_settings()
    expires = get_datetime(doc.creation) + timedelta(days=settings.published_ctrack_days)
    if doc.status == st.DELIVERED and doc.delivery_date_time:
        expires = min(expires, get_datetime(doc.delivery_date_time)
                      + timedelta(days=settings.unpublish_after_delivery_days))
    return expires


def sign(name: str, exp: int) -> str:
    key = hmac.new(get_encryption_key().encode(), SALT, hashlib.sha256).digest()
    return hmac.new(key, f"{name}:{exp}".encode(), hashlib.sha256).hexdigest()


def signed_url(doc, settings: Optional[ShippingSettings] = None) -> str:
    exp = int(access_expires_on(doc, settings).timestamp())
    return get_url(f"/{doc.route}?exp={exp}&sig={sign(doc.name, exp)}")


def has_valid_signature(doc, args, now=None, settings: Optional[ShippingSettings] = None) -> bool:
    """`args` is the URL query (request.args), never the merged form data. The link is
    good until its own exp or the current expiry of the tracking, if that is earlier."""
    sig, exp = args.get("sig"), args.get("exp")
    if not isinstance(sig, str) or not isinstance(exp, str) or not exp.isdigit():
        return False
    if not hmac.compare_digest(sign(doc.name, cint(exp)), sig):
        return False
    now = get_datetime(now or now_datetime())
    return now.timestamp() <= cint(exp) and now <= access_expires_on(doc, settings)


def can_view(doc, args=None, user: Optional[str] = None, now=None) -> bool:
    """Signed link first (no query), then the logged-in user checks. The expiry applies to
    everyone: desk users still open the document in the desk."""
    settings = get_shipping_settings()
    now = get_datetime(now or now_datetime())
    if now > access_expires_on(doc, settings):
        return False
    if args is not None and has_valid_signature(doc, args, now, settings):
        return True
    user = user or frappe.session.user
    if user == "Guest":
        return False
    return is_receiver_contact(doc, user) or frappe.has_permission(doc.doctype, "read", doc, user=user)


def is_receiver_contact(doc, user: str) -> bool:
    """One query: a Contact of the user with a Dynamic Link to the receiver."""
    if not (doc.receiver_document and doc.receiver_name):
        return False
    contact, link = frappe.qb.DocType("Contact"), frappe.qb.DocType("Dynamic Link")
    rows = (
        frappe.qb.from_(contact)
        .join(link).on((link.parent == contact.name) & (link.parenttype == "Contact"))
        .select(contact.name)
        .where(contact.user == user)
        .where(link.link_doctype == doc.receiver_document)
        .where(link.link_name == doc.receiver_name)
        .limit(1)
    ).run()
    return bool(rows)


def request_args():
    """The URL query of the web request, or None outside a request."""
    request = getattr(frappe.local, "request", None)
    return request.args if request is not None else None
