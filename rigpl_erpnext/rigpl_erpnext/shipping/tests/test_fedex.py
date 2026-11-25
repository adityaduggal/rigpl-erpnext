"""FedEx REST adapter (#170): bodies and parsers on JSON fixtures, HTTP mocked. No database."""
import json
import os
from datetime import date, datetime
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.base import (Account, Address, BookingResult, Commodity, NotSupported, Package,
                                                       PreviewContext, ProviderError, ShipmentRequest, TradeDocument)
from rigpl_erpnext.rigpl_erpnext.shipping.http import clear_token
from rigpl_erpnext.rigpl_erpnext.shipping.providers import fedex
from rigpl_erpnext.rigpl_erpnext.shipping.providers import fedex_payloads as fp

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "fedex")
TZ = "Asia/Kolkata"
DOCUMENTS = [TradeDocument("COMMERCIAL_INVOICE", "SI-0001.pdf", b"%PDF-1.4"),
             TradeDocument("OTHER", "packing.png", b"PNG", "image/png")]
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
        self.assertNotIn("shippingDocumentSpecification", req)  # FedEx makes no invoice: we upload ours
        self.assertNotIn("shipmentSpecialServices", req)  # no uploaded documents, no ETD

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

    def test_eu_destination_gets_the_product_id_on_each_line(self):
        items = [Commodity("End Mill", 10, "Nos", 60, 1.0, "820770", "IN", "EM-" + "X" * 80),
                 Commodity("Drill", 4, "Nos", 100, 1.0, "820750", "IN")]
        lines = fp.customs_lines(shipment(destination=address(country_code="DE"), commodities=items))
        sku = ("EM-" + "X" * 80)[:70]
        self.assertEqual(lines[0]["regulatoryDetails"], [{"regulationCode": "EU_DE_MINIMIS", "productId": sku,
                                                          "productIdType": "SKU", "details": {"merchantProductId": sku}}])
        self.assertNotIn("regulatoryDetails", lines[1])  # no item code, nothing to send

    def test_non_eu_destination_and_non_sale_lines_have_no_product_id(self):
        items = [Commodity("End Mill", 10, "Nos", 60, 1.0, "820770", "IN", "EM-1")]
        self.assertNotIn("regulatoryDetails", fp.customs_lines(shipment(commodities=items))[0])
        eu = address(country_code="FR")
        self.assertNotIn("regulatoryDetails", fp.customs_lines(shipment(destination=eu, commodities=items,
                                                                        purpose="SAMPLE"))[0])
        self.assertNotIn("regulatoryDetails", fp.customs_lines(shipment(destination=eu, commodities=[]))[0])

    def test_preview_of_each_action_has_the_url_and_body_and_sends_nothing(self):
        awb = "794600000001"
        docs = [TradeDocument("COMMERCIAL_INVOICE", "SI-0001.pdf", b"%PDF" + b"x" * 500)]
        ctx = PreviewContext(request=shipment(documents=docs), awb=awb, reference="CTRACK1")
        actions = ("get_rates", "book_shipment", "available_services", "address_validation", "get_status", "get_pod",
                   "delete_shipment")
        with patch("requests.Session.request", side_effect=AssertionError("sent")):
            calls = {action: adapter().preview(action, ctx) for action in actions}
        for steps in calls.values():
            self.assertEqual(steps[0]["step"], "Login (only when the token has expired)")
            self.assertTrue(all(c["url"].startswith(fedex.PRODUCTION_URL) or c["url"].startswith(fedex.DOCUMENT_URL)
                                for c in steps))
        book = calls["book_shipment"]
        self.assertEqual([c["step"] for c in book[1:]], ["Rate", "Upload documents", "Ship"])
        self.assertEqual(book[-1]["url"], fedex.PRODUCTION_URL + fedex.SHIP_PATH)
        self.assertEqual(book[-1]["body"]["requestedShipment"]["serviceType"], "INTERNATIONAL_PRIORITY")
        self.assertEqual(book[2]["url"], fedex.DOCUMENT_URL + fedex.UPLOAD_PATH)
        self.assertRegex(book[2]["body"]["metaData"][0]["fileContentBase64"], r"^<\d+ characters>$")
        self.assertEqual((calls["delete_shipment"][-1]["method"], calls["delete_shipment"][-1]["url"]),
                         ("PUT", fedex.PRODUCTION_URL + fedex.CANCEL_PATH))
        self.assertIn(awb, str(calls["get_status"][-1]["body"]))
        self.assertNotIn("'secret'", str(calls))  # the Client Secret of the account

    def test_preview_of_an_unknown_action_is_not_supported(self):
        with self.assertRaises(NotSupported):
            adapter().preview("get_labels", PreviewContext(request=shipment()))

    def test_block_switch_stops_every_call_and_shows_the_body(self):
        from rigpl_erpnext.rigpl_erpnext.shipping.base import ProviderError

        old = frappe.conf.get("shipping_block_calls")
        frappe.conf.shipping_block_calls = 1
        try:
            with patch("requests.Session.request", side_effect=AssertionError("sent")):
                with self.assertRaises(ProviderError) as ctx:
                    adapter().get_rates(shipment())
        finally:
            frappe.conf.shipping_block_calls = old
        self.assertIn("calls are blocked", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))

    def test_domestic_shipment_sends_no_invoice_reference(self):
        body = fp.ship_body(shipment(destination=address(country_code="IN")), "1")
        self.assertNotIn("customerReferences", body["requestedShipment"]["customsClearanceDetail"]["commercialInvoice"])

    def test_upload_sends_each_document_in_one_call(self):
        body = fp.upload_body(shipment(documents=DOCUMENTS))
        self.assertEqual((body["workflowName"], body["carrierCode"], body["originCountryCode"],
                          body["destinationCountryCode"]), ("ETDPreshipment", "FDXE", "IN", "US"))
        self.assertEqual([(m["fileReferenceId"], m["shipDocumentType"], m["contentType"]) for m in body["metaData"]],
                         [("CTRACK-T1-1", "COMMERCIAL_INVOICE", "application/pdf"),
                          ("CTRACK-T1-2", "OTHER", "image/png")])
        self.assertEqual(body["metaData"][0]["fileContentBase64"], "JVBERi0xLjQ=")

    def test_upload_reply_gives_the_doc_ids_in_order(self):
        reply = {"output": {"documentResponses": [
            {"fileReferenceId": "CTRACK-T1-2", "metaData": {"documentType": "OTHER", "docId": "D2"}},
            {"fileReferenceId": "CTRACK-T1-1", "metaData": {"documentType": "CI", "docId": "D1"}}]}}
        self.assertEqual(fp.parse_upload(reply, shipment(documents=DOCUMENTS)), ["D1", "D2"])
        self.assertEqual(fp.parse_upload({"output": {}}, shipment(documents=DOCUMENTS)), [None, None])

    def test_export_with_uploaded_documents_asks_for_etd(self):
        req = fp.ship_body(shipment(documents=DOCUMENTS), "1", ["D1", "D2"])["requestedShipment"]
        self.assertEqual(req["shipmentSpecialServices"], {
            "specialServiceTypes": ["ELECTRONIC_TRADE_DOCUMENTS"],
            "etdDetail": {"attachedDocuments": [
                {"documentType": "COMMERCIAL_INVOICE", "documentReference": "SI-0001", "description": "SI-0001.pdf",
                 "documentId": "D1"},
                {"documentType": "OTHER", "documentReference": "SI-0001", "description": "packing.png",
                 "documentId": "D2"}]}})


    def test_export_clearance_line_goes_in_the_commercial_invoice_of_an_export_only(self):
        line = "CSB-V. IEC 0500000001."
        invoice = fp.ship_body(shipment(special_instructions=line), "1")["requestedShipment"][
            "customsClearanceDetail"]["commercialInvoice"]
        self.assertEqual(invoice["specialInstructions"], line)
        domestic = fp.ship_body(shipment(special_instructions=line, destination=address(country_code="IN")), "1")
        self.assertNotIn("specialInstructions", domestic["requestedShipment"]["customsClearanceDetail"]["commercialInvoice"])
        self.assertNotIn("specialInstructions", fp.rate_body(shipment(special_instructions=line), "1")[
            "requestedShipment"]["customsClearanceDetail"]["commercialInvoice"])


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
        self.assertEqual((result.etd_type, result.invoice_copies), ("", 0))

    def test_ship_reply_with_originals_gives_the_invoice_copies(self):
        """The paths are from the FedEx Ship API OpenAPI file (#240)."""
        reply = fixture("ship")
        detail = reply["output"]["transactionShipments"][0]["completedShipmentDetail"]
        detail["completedEtdDetail"] = {"folderId": "F1", "type": "COMMERCIAL_INVOICE", "uploadDocumentReferenceDetails": [
            {"documentType": "COMMERCIAL_INVOICE", "documentId": "D1"}, {"documentType": "OTHER", "documentId": "D2"}]}
        detail["documentRequirements"] = {"requiredDocuments": ["COMMERCIAL_OR_PRO_FORMA_INVOICE", "AIR_WAYBILL"],
                                          "generationDetails": [{"type": "COMMERCIAL_INVOICE", "minimumCopiesRequired": 3},
                                                                {"type": "AIR_WAYBILL", "minimumCopiesRequired": 5}]}
        result = fp.parse_ship(reply, "CTRACK-T1")
        self.assertEqual((result.etd_type, result.invoice_copies), ("COMMERCIAL_INVOICE, OTHER", 3))

        detail["documentRequirements"]["generationDetails"][0]["minimumCopiesRequired"] = 0
        self.assertEqual(fp.parse_ship(reply, "CTRACK-T1").invoice_copies, 0)  # electronic only

    def test_booking_message_says_what_to_print(self):
        from rigpl_erpnext.rigpl_erpnext.shipping.actions import invoice_note

        self.assertIn("Print 2 copies", invoice_note(BookingResult("1", [], etd_type="COMMERCIAL_INVOICE", invoice_copies=2)))
        self.assertIn("No paper copy", invoice_note(BookingResult("1", [], etd_type="COMMERCIAL_INVOICE")))
        self.assertEqual(invoice_note(BookingResult("1", [])), "")

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
        self.assertEqual(adapter(is_sandbox=True).document_url, fedex.DOCUMENT_SANDBOX_URL)

    def test_export_booking_uploads_the_documents_first(self):
        upload = {"output": {"documentResponses": [{"fileReferenceId": "CTRACK-T1-1", "metaData": {"docId": "D1"}},
                                                   {"fileReferenceId": "CTRACK-T1-2", "metaData": {"docId": "D2"}}]}}
        replies = [Reply({"access_token": "T", "expires_in": 3600}), Reply(upload, 201), Reply(fixture("ship"))]
        with patch(f"{MODULE}.request", side_effect=replies) as request:
            result = adapter().book(shipment(documents=DOCUMENTS))
        self.assertEqual(result.awb, "100000000010")
        upload_call, ship_call = request.call_args_list[1:]
        self.assertEqual(upload_call.args[1], fedex.DOCUMENT_URL + "/documents/v1/etds/encodedmultiupload")
        self.assertEqual(ship_call.args[1], fedex.PRODUCTION_URL + "/ship/v1/shipments")
        attached = ship_call.kwargs["json"]["requestedShipment"]["shipmentSpecialServices"]["etdDetail"]["attachedDocuments"]
        self.assertEqual([a["documentId"] for a in attached], ["D1", "D2"])

    def test_a_refused_document_stops_the_booking(self):
        upload = {"output": {"documentResponses": [{"fileReferenceId": "CTRACK-T1-1", "metaData": {"docId": "D1"}}]}}
        replies = [Reply({"access_token": "T", "expires_in": 3600}), Reply(upload, 201)]
        with patch(f"{MODULE}.request", side_effect=replies) as request, self.assertRaises(ProviderError) as ctx:
            adapter().book(shipment(documents=DOCUMENTS))
        self.assertIn("packing.png", str(ctx.exception))
        self.assertEqual(len(request.call_args_list), 2)  # no booking call


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


class TestTradeDocuments(FrappeTestCase):
    """The checks on the attached files before an export booking (#240). File reads are mocked."""

    def documents(self, files, **fields):
        import frappe
        from rigpl_erpnext.rigpl_erpnext.shipping import request

        doc = frappe.new_doc("Carrier Tracking")
        doc.update(dict(name="CTRACK-T1", purpose="SOLD", customs_invoice="/private/files/SI-0001.pdf"))
        doc.update(fields)
        by_url = {url: frappe._dict(file_name=url.rsplit("/", 1)[-1], get_content=lambda c=content: c)
                  for url, content in files.items()}
        with patch.object(frappe.db, "get_value", side_effect=lambda dt, filters, field: filters["file_url"]
                          if filters["file_url"] in by_url else None), \
                patch.object(frappe, "get_doc", side_effect=lambda dt, name: by_url[name]):
            return request.trade_documents(doc)

    def test_sale_sends_a_commercial_invoice_and_others_a_pro_forma(self):
        pdf = {"/private/files/SI-0001.pdf": b"%PDF-1.4 x"}
        self.assertEqual([d.doc_type for d in self.documents(pdf)], ["COMMERCIAL_INVOICE"])
        self.assertEqual([d.doc_type for d in self.documents(pdf, purpose="SAMPLE")], ["PRO_FORMA_INVOICE"])
        both = dict(pdf, **{"/private/files/packing.xlsx": b"PK"})
        docs = self.documents(both, other_trade_document="/private/files/packing.xlsx")
        self.assertEqual([(d.doc_type, d.filename) for d in docs],
                         [("COMMERCIAL_INVOICE", "SI-0001.pdf"), ("OTHER", "packing.xlsx")])
        self.assertTrue(docs[1].content_type.endswith("spreadsheetml.sheet"))

    def test_missing_wrong_or_large_files_stop_the_booking(self):
        import frappe

        cases = [({}, {"customs_invoice": ""}, "Attach the invoice PDF"),
                 ({}, {}, "attach the file again"),
                 ({"/private/files/SI-0001.pdf": b"not a pdf"}, {}, "must be a PDF"),
                 ({"/private/files/SI-0001.pdf": b"%PDF" + b"x" * (5 * 1024 * 1024)}, {}, "at most 5 MB"),
                 ({"/private/files/SI-0001.pdf": b"%PDF", "/private/files/a.exe": b"MZ"},
                  {"other_trade_document": "/private/files/a.exe"}, "does not take .exe")]
        for files, fields, message in cases:
            with self.subTest(message), self.assertRaises(frappe.ValidationError) as ctx:
                self.documents(files, **fields)
            self.assertIn(message, str(ctx.exception))


class TestInvoiceCommodities(FrappeTestCase):
    """The invoice table that goes to the carrier (#243). No database."""
    ROW = dict(item_code=None, item_name=None, qty=2460, uom="Nos", amount=22756.4, gst_hsn_code="82090090",
               total_weight=0)

    def commodities(self, setting, rows):
        import frappe
        from rigpl_erpnext.rigpl_erpnext.shipping import request

        def get_all(doctype, **kw):
            if doctype != "Sales Invoice Item":
                return []
            self.filters = kw["filters"]
            return [frappe._dict(r) for r in rows]

        doc = frappe._dict(document="Sales Invoice", document_name="SI-0001")
        with patch.object(frappe, "get_all", side_effect=get_all), \
                patch.object(frappe, "get_cached_value", return_value=setting), \
                patch.object(frappe, "get_desk_link", side_effect=lambda dt, name: name):
            return request.load_commodities(doc)

    def test_setting_selects_one_table_and_empty_means_synopsis(self):
        for setting, table in ((None, "items_synopsis"), ("", "items_synopsis"),
                               ("Item Synopsis", "items_synopsis"), ("Items", "items")):
            with self.subTest(setting=setting):
                self.commodities(setting, [self.ROW])
                self.assertEqual(self.filters["parentfield"], table)

    def test_value_of_a_line_is_the_row_amount(self):
        line = self.commodities(None, [self.ROW])[0]
        self.assertEqual(round(line.unit_price * line.quantity, 2), 22756.4)
        self.assertEqual(line.description, "Cutting Tools")  # no HSN text, name or code

    def test_empty_table_stops_with_the_invoice_and_the_setting(self):
        import frappe

        with self.assertRaisesRegex(frappe.ValidationError,
                                    "SI-0001 has no rows in Item Synopsis.*Sales Invoice Table for Carriers"):
            self.commodities(None, [])


class TestExportClearance(FrappeTestCase):
    """CSB-IV, CSB-V or Shipping Bill of an export, and the line for the carrier (#241). No database."""
    TEMPLATE = dict(iec_code="0500000001", bank_ad_code="01234560000001", export_type="Without Payment of Tax",
                    lut_no_and_date="AD0603240012345 01-04-2026")

    def test_sale_up_to_10_lakh_is_csb_v_above_is_a_shipping_bill_and_samples_are_csb_iv(self):
        from rigpl_erpnext.rigpl_erpnext.shipping import request

        self.assertEqual(request.export_clearance("SOLD", 1000000), "CSB-V")
        self.assertEqual(request.export_clearance("SOLD", 1000000.01), "Shipping Bill")
        self.assertEqual(request.export_clearance("", 500), "CSB-V")
        self.assertEqual(request.export_clearance("SOLD", None), "")
        for purpose in ("SAMPLE", "GIFT", "NOT_SOLD", "REPAIR_AND_RETURN"):
            self.assertEqual(request.export_clearance(purpose, 2000000), "CSB-IV")

    def test_clearance_line_names_iec_ad_code_gstin_and_lut(self):
        from rigpl_erpnext.rigpl_erpnext.shipping import request

        self.assertEqual(request.clearance_line("CSB-V", self.TEMPLATE, "06AAAAA0000A1Z5", "SOLD"),
                         "CSB-V. IEC 0500000001. AD Code 01234560000001. GSTIN 06AAAAA0000A1Z5. "
                         "Export under LUT AD0603240012345 01-04-2026 without IGST.")
        paid = dict(self.TEMPLATE, export_type="With Payment of Tax")
        self.assertTrue(request.clearance_line("Shipping Bill", paid, "NA", "SOLD").startswith(
            "Shipping Bill. Value above Rs 10 lakh, formal clearance. IEC"))
        self.assertTrue(request.clearance_line("Shipping Bill", paid, "NA", "SOLD").endswith(
            "AD Code 01234560000001. Export with payment of IGST."))
        self.assertEqual(request.clearance_line("CSB-IV", {}, "06AAAAA0000A1Z5", "REPAIR_AND_RETURN"),
                         "CSB-IV. Repair And Return, not for sale. GSTIN 06AAAAA0000A1Z5.")
        self.assertEqual(request.clearance_line("CSB-V", dict(self.TEMPLATE, lut_no_and_date="NA"), "", "SOLD"),
                         "CSB-V. IEC 0500000001. AD Code 01234560000001. Export under LUT without IGST.")

    def instructions(self, template, gstin="06AAAAA0000A1Z5", **fields):
        import frappe
        from rigpl_erpnext.rigpl_erpnext.shipping import request

        doc = frappe._dict(name="CTRACK-T1", purpose="SOLD", document="Sales Invoice", document_name="SI-0001",
                           from_address="RIGPL-Billing", export_clearance="CSB-V")
        doc.update(fields)
        values = {"Sales Invoice": "RIGB Export Under Bond",
                  "Sales Taxes and Charges Template": frappe._dict(template) if template is not None else None}
        req = shipment(origin=address(country_code="IN", tax_id=gstin))
        with patch.object(frappe.db, "get_value", side_effect=lambda dt, name, field, **kw: values[dt]), \
                patch.object(frappe, "get_desk_link", side_effect=lambda dt, name: name):
            return request.export_instructions(doc, req)

    def test_sale_needs_iec_ad_code_export_type_and_gstin(self):
        import frappe

        self.assertTrue(self.instructions(self.TEMPLATE).startswith("CSB-V. IEC 0500000001."))
        with self.assertRaisesRegex(frappe.ValidationError, "needs Bank AD Code, Export Type, GSTIN of From Address"):
            self.instructions(dict(self.TEMPLATE, bank_ad_code="", export_type=None), gstin="NA")
        with self.assertRaisesRegex(frappe.ValidationError, "needs IEC Code, Bank AD Code, Export Type"):
            self.instructions(None)

    def test_sample_needs_no_template(self):
        self.assertEqual(self.instructions(None, purpose="SAMPLE", export_clearance="CSB-IV", document="Customer"),
                         "CSB-IV. Sample, not for sale. GSTIN 06AAAAA0000A1Z5.")
