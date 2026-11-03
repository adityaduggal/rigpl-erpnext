"""FedEx REST adapter (#170): bodies and parsers on JSON fixtures, HTTP mocked. No database."""
import json
import os
from datetime import date, datetime
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.base import Account, Address, Commodity, Package, ProviderError, ShipmentRequest
from rigpl_erpnext.rigpl_erpnext.shipping.http import clear_token
from rigpl_erpnext.rigpl_erpnext.shipping.providers import fedex
from rigpl_erpnext.rigpl_erpnext.shipping.providers import fedex_payloads as fp

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fedex")
TZ = "Asia/Kolkata"
MODULE = "rigpl_erpnext.rigpl_erpnext.shipping.providers.fedex"


def fixture(name):
    with open(os.path.join(FIXTURES, name + ".json")) as f:
        return json.load(f)


class Reply:
    def __init__(self, data, status_code=200):
        self.data, self.status_code = data, status_code
        self.text, self.url = json.dumps(data), "https://apis.fedex.com/x"
        self.request = type("R", (), {"method": "POST"})

    def json(self):
        return self.data


def address(**kw):
    values = dict(name="Buyer Inc", line1="1 Main Street", line2="Suite 2", city="Springfield", state_code="MA",
                  pincode="01101", country="United States", country_code="US", phone="+1 (413) 555-0100",
                  contact="A Buyer", company="Buyer Inc", tax_id="NA")
    values.update(kw)
    return Address(**values)


def shipment(**kw):
    values = dict(
        reference="CTRACK-T1", service_code="INTERNATIONAL_PRIORITY",
        origin=address(name="RIGPL", city="New Delhi", state_code="DL", pincode="110001", country="India",
                       country_code="IN", tax_id="06AAAAA0000A1Z5"),
        destination=address(),
        packages=[Package(weight=2.5, length=30, width=20, height=10), Package(weight=1.25)],
        declared_value=1000, currency="USD", invoice_number="SI-0001", purchase_order="PO/12-34 abc",
        commodities=[Commodity("End Mill", 10, "Nos", 60, 0.0, "8207.70", "IN"),
                     Commodity("Drill", 4, "Nos", 100, 1.0, "820750", "IN")],
        ship_date=date(2026, 11, 3),
    )
    values.update(kw)
    return ShipmentRequest(**values)


def adapter(**kw):
    values = dict(name="_Test FedEx", provider="FedEx", account_number="000000000", client_id="id",
                  client_secret="secret")
    values.update(kw)
    return fedex.FedEx(Account(**values))


class TestFedExBodies(FrappeTestCase):
    def test_ship_body_sends_all_packages_in_one_request(self):
        body = fp.ship_body(shipment(test_marking=True), "000000000")
        req = body["requestedShipment"]
        self.assertEqual(req["totalPackageCount"], 2)
        self.assertEqual([p["sequenceNumber"] for p in req["requestedPackageLineItems"]], [1, 2])
        self.assertNotIn("dimensions", req["requestedPackageLineItems"][1])
        refs = {r["customerReferenceType"]: r["value"] for r in req["requestedPackageLineItems"][0]["customerReferences"]}
        self.assertEqual(refs, {"CUSTOMER_REFERENCE": "TEST-RIGPL-CTRACK-T1", "P_O_NUMBER": "PO1234abc",
                                "INVOICE_NUMBER": "SI-0001"})
        self.assertEqual(req["shippingChargesPayment"]["paymentType"], "SENDER")
        self.assertEqual(req["customsClearanceDetail"]["dutiesPayment"], {"paymentType": "RECIPIENT"})
        self.assertEqual(req["shippingDocumentSpecification"]["shippingDocumentTypes"], ["COMMERCIAL_INVOICE"])

    def test_party_skips_na_tin_and_cuts_to_fedex_limits(self):
        result = fp.party(address(line1="x" * 50, phone="+1 (413) 555-0100"))
        self.assertNotIn("tins", result)
        self.assertEqual(len(result["address"]["streetLines"][0]), 35)
        self.assertEqual(result["contact"]["phoneNumber"], "+14135550100")
        self.assertEqual(fp.party(shipment().origin)["tins"][0]["tinType"], "BUSINESS_NATIONAL")

    def test_customs_lines_spread_the_missing_weight_and_sum_the_value(self):
        customs = fp.ship_body(shipment(), "000000000")["requestedShipment"]["customsClearanceDetail"]
        lines = customs["commodities"]
        self.assertEqual([l["weight"]["value"] for l in lines], [2.75, 1.0])  # 3.75 kg less the known 1 kg
        self.assertEqual(customs["totalCustomsValue"], {"amount": 1000.0, "currency": "USD"})
        self.assertEqual(lines[0]["harmonizedCode"], "820770")

    def test_non_sale_has_one_line_of_value_1_and_no_items_gives_printed_matter(self):
        sample = fp.customs_lines(shipment(purpose="SAMPLE"))
        self.assertEqual((len(sample), sample[0]["customsValue"]["amount"]), (1, 1.0))
        printed = fp.customs_lines(shipment(commodities=[]))
        self.assertEqual(printed[0]["harmonizedCode"], "49111010")
        self.assertNotIn("shippingDocumentSpecification",
                         fp.ship_body(shipment(purpose="SAMPLE"), "1")["requestedShipment"])

    def test_domestic_shipment_has_no_commercial_invoice_document(self):
        body = fp.ship_body(shipment(destination=address(country_code="IN")), "1")
        self.assertNotIn("shippingDocumentSpecification", body["requestedShipment"])


class TestFedExReplies(FrappeTestCase):
    def test_rates_flag_oda_and_read_transit_days(self):
        rates = fp.parse_rates(fixture("rate"))
        self.assertEqual([(r.service_code, r.amount, r.oda, r.transit_days) for r in rates],
                         [("INTERNATIONAL_PRIORITY", 8450.5, True, 3), ("INTERNATIONAL_ECONOMY", 6100.0, False, 5)])
        self.assertEqual([r.delivery_date for r in rates], [date(2026, 11, 6), None])

    def test_transit_lines_show_the_commit_day(self):
        self.assertEqual(fp.parse_transit(fixture("transit")), [
            "FedEx International Priority: Fri Nov-06-2026 17:00", "FedEx International Economy: no commit date"])

    def test_ship_reply_gives_awb_pieces_labels_and_invoice(self):
        result = fp.parse_ship(fixture("ship"), "CTRACK-T1")
        self.assertEqual((result.awb, result.package_ids, result.cost), ("100000000010", ["100000000010", "100000000011"], 8450.5))
        self.assertEqual([l.filename for l in result.labels], ["FEDEX-100000000010.pdf", "FEDEX-100000000011.pdf",
                                                               "COMMER-INV-CTRACK-T1-100000000010.pdf"])
        self.assertTrue(result.labels[0].content.startswith(b"%PDF"))

    def test_tracking_delivered_in_transit_and_not_found(self):
        items = fp.track_items(fixture("track"))
        resolve = adapter().resolve
        delivered = fp.parse_tracking("100000000001", items["100000000001"], resolve, TZ)
        self.assertEqual((delivered.status, delivered.status_code, delivered.recipient), (st.DELIVERED, "DL", "A.PERSON"))
        self.assertEqual(delivered.delivery_date_time, datetime(2026, 10, 16, 21, 17))  # 11:47 -04:00 in IST
        self.assertEqual(delivered.pickup_date, datetime(2026, 10, 12, 15, 26))
        self.assertTrue(delivered.pod_available)
        self.assertEqual(delivered.scans[0].status_detail, "PU: Picked up")
        self.assertEqual(delivered.destination, "SPRINGFIELD, MA, United States")

        transit = fp.parse_tracking("100000000002", items["100000000002"], resolve, TZ)
        self.assertEqual((transit.status, transit.delivery_date_time, transit.pod_available), (st.IN_TRANSIT, None, False))
        self.assertEqual(transit.expected_delivery_date, date(2026, 10, 18))
        self.assertIn("Excep Code: 08 Recipient not in", transit.scans[-1].status_detail)

        missing = fp.parse_tracking("100000000003", items["100000000003"], resolve, TZ)
        self.assertEqual((missing.status, missing.found), (st.NO_INFORMATION, False))
        self.assertFalse(fp.parse_tracking("X", None, resolve, TZ).found)

    def test_pod_reply_gives_a_pdf(self):
        label = fp.parse_pod("100000000001", fixture("pod"))
        self.assertEqual(label.filename, "POD-100000000001.pdf")
        self.assertIsNone(fp.parse_pod("1", {"output": {"documents": []}}))


class TestFedExHTTP(FrappeTestCase):
    def setUp(self):
        clear_token("fedex:_Test FedEx")

    def tearDown(self):
        clear_token("fedex:_Test FedEx")

    def test_65_awbs_take_3_track_calls_and_one_login(self):
        token = Reply({"access_token": "T", "expires_in": 3600})
        with patch(f"{MODULE}.request", side_effect=[token] + [Reply(fixture("track"))] * 3) as request:
            results = adapter().track_many({str(n): f"CT{n}" for n in range(65)})
        paths = [c.args[1].rsplit("/", 2)[-1] for c in request.call_args_list]
        self.assertEqual(paths, ["token", "trackingnumbers", "trackingnumbers", "trackingnumbers"])
        self.assertEqual(len(request.call_args_list[-1].kwargs["json"]["trackingInfo"]), 5)
        self.assertEqual(len(results), 65)
        self.assertFalse(results["0"].found)  # not in the reply

    def test_token_is_fetched_once_for_many_calls(self):
        from rigpl_erpnext.rigpl_erpnext.shipping.http import cached_token

        calls = []

        def fetch():
            calls.append(1)
            return "T", 3600

        self.assertEqual([cached_token("fedex:_Test FedEx", fetch) for _ in range(3)], ["T", "T", "T"])
        self.assertEqual(len(calls), 1)

    def test_401_renews_the_token_once(self):
        replies = [Reply({"access_token": "OLD", "expires_in": 3600}), Reply({}, 401),
                   Reply({"access_token": "NEW", "expires_in": 3600}), Reply(fixture("cancel"))]
        with patch(f"{MODULE}.request", side_effect=replies) as request:
            adapter().cancel("100000000010")
        self.assertEqual(request.call_args_list[-1].kwargs["headers"]["Authorization"], "Bearer NEW")
        self.assertEqual(request.call_args_list[-1].args[0], "PUT")

    def test_fedex_errors_raise_without_the_secret(self):
        replies = [Reply({"access_token": "T", "expires_in": 3600}), Reply(fixture("errors"), 403)]
        with patch(f"{MODULE}.request", side_effect=replies), self.assertRaises(ProviderError) as ctx:
            adapter().book(shipment())
        self.assertIn("SHIPMENT.USER.UNAUTHORIZED", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))

    def test_missing_keys_name_the_account(self):
        with patch(f"{MODULE}.request") as request, self.assertRaises(ProviderError) as ctx:
            adapter(client_secret="").get_pod("1")
        request.assert_not_called()
        self.assertIn("_Test FedEx", str(ctx.exception))

    def test_sandbox_url(self):
        self.assertEqual(adapter(is_sandbox=True).base_url, fedex.SANDBOX_URL)
        self.assertEqual(adapter().base_url, fedex.PRODUCTION_URL)


class TestShipmentRequestAddresses(FrappeTestCase):
    def test_the_contact_goes_only_on_the_receiver_address(self):
        import frappe
        from rigpl_erpnext.rigpl_erpnext.shipping import request

        rows = [frappe._dict(name=n, address_title=n, address_line1="1 Road", address_line2="", city="C", state="",
                             state_rigpl=s, pincode="1", country=c, phone="", email_id="", gstin="")
                for n, s, c in (("FROM", "Haryana", "India"), ("TO", "", "United States"))]
        tables = {"Address": rows, "Country": [("India", "in"), ("United States", "us")], "State": [("Haryana", "HR ")]}
        contact = frappe._dict(first_name="A", last_name="Buyer", mobile_no="99", phone="", email_id="a@b.c")
        with patch.object(frappe, "get_all", side_effect=lambda doctype, **kw: tables[doctype]), \
                patch.object(frappe.db, "get_value", return_value=contact):
            result = request.load_addresses(["FROM", "TO"], "CONTACT-1", "TO")
        self.assertEqual((result["FROM"].contact, result["FROM"].phone, result["FROM"].state_code), ("FROM", "", "HR"))
        self.assertEqual((result["TO"].contact, result["TO"].phone, result["TO"].country_code), ("A Buyer", "99", "US"))
