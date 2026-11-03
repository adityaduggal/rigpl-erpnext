"""Pure tests of the adapters and the status map: synthetic replies, no HTTP, no database."""
from datetime import datetime

from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.rigpl_erpnext.shipping import status as st
from rigpl_erpnext.rigpl_erpnext.shipping.base import Account, Address, Package, ShipmentRequest
from rigpl_erpnext.rigpl_erpnext.shipping.providers import dtdc, shipway
from rigpl_erpnext.rigpl_erpnext.shipping.seed_rules import SEED_RULES
from rigpl_erpnext.rigpl_erpnext.shipping.status_map import CODE, STARTS_WITH, TEXT, StatusResolver, match, seed_rules


def dtdc_scan(code, action, day, time):
    return {"strCode": code, "strAction": action, "strManifestNo": "M1", "sTrRemarks": "", "strActionDate": day,
            "strActionTime": time, "strOrigin": "DELHI", "strDestination": "CHENNAI"}


def dtdc_reply(*scans, header_status="In Transit", delivered_on="", delivered_at=""):
    return {
        "statusCode": 200,
        "trackHeader": {"strStatus": header_status, "strDestination": "CHENNAI", "strBookedDate": "13102026",
                        "strBookedTime": "20:36:00", "strExpectedDeliveryDate": "15102026",
                        "strStatusTransOn": delivered_on, "strStatusTransTime": delivered_at,
                        "strRemarks": "Recd by", "strStatusRelName": "A Person"},
        "trackDetails": list(scans),
    }


def dtdc_resolver():
    return StatusResolver("DTDC", rules=seed_rules("DTDC", SEED_RULES["DTDC"]))


class TestStatusMap(FrappeTestCase):
    RULES = [(CODE, "DLV", st.DELIVERED), (STARTS_WITH, "RTO", st.RTO), (TEXT, "DELIVERED", st.DELIVERED),
             (TEXT, "UNDELIVERED", st.EXCEPTION), (CODE, "NEW", "")]

    def test_code_rows_win_then_the_longest_match(self):
        self.assertEqual(match(self.RULES, "dlv", "Undelivered")[2], st.DELIVERED)
        self.assertEqual(match(self.RULES, "RTOIN", "")[2], st.RTO)
        self.assertEqual(match(self.RULES, "X", "Shipment Undelivered")[2], st.EXCEPTION)
        self.assertEqual(match(self.RULES, "X", "OTP Based Delivered")[2], st.DELIVERED)
        self.assertIsNone(match(self.RULES, "X", "In Transit"))

    def test_unknown_codes_are_collected_and_unmapped_rows_give_none(self):
        resolve = StatusResolver("DTDC", rules=self.RULES)
        self.assertIsNone(resolve("ABC", "Some new text"))
        self.assertIsNone(resolve("NEW", ""))  # in the map, but no status yet: not collected again
        self.assertEqual(resolve.unknown, {"ABC": "Some new text"})


class TestDTDC(FrappeTestCase):
    def test_latest_scan_code_gives_the_status_and_dates(self):
        reply = dtdc_reply(
            dtdc_scan("PCUP", "Picked Up", "13102026", "2040"),
            dtdc_scan("DLV", "OTP Based Delivered", "15102026", "1707"),
            dtdc_scan("OUTDLV", "Out For Delivery", "15102026", "0900"),
            header_status="Delivered", delivered_on="15102026", delivered_at="1707",
        )
        result = dtdc.parse_tracking("D1", reply, dtdc_resolver())
        self.assertEqual((result.status, result.status_code), (st.DELIVERED, "DLV"))
        self.assertEqual(result.delivery_date_time, datetime(2026, 10, 15, 17, 7))
        self.assertEqual(result.pickup_date, datetime(2026, 10, 13, 20, 36))
        self.assertEqual(str(result.expected_delivery_date), "2026-10-15")
        self.assertEqual([s.status_detail.split(":")[0] for s in result.scans], ["PCUP", "OUTDLV", "DLV"])
        self.assertEqual(result.recipient, "Recd by A Person")

    def test_rto_misroute_and_unknown_codes(self):
        resolve = dtdc_resolver()
        rto = dtdc.parse_tracking("D2", dtdc_reply(dtdc_scan("SETRTO", "Set RTO", "14102026", "1000")), resolve)
        self.assertEqual(rto.status, st.RTO)
        self.assertIsNone(rto.delivery_date_time)
        hub = dtdc.parse_tracking("D3", dtdc_reply(dtdc_scan("RTRB", "Return", "14102026", "1000")), resolve)
        self.assertEqual(hub.status, st.EXCEPTION)
        new = dtdc.parse_tracking("D4", dtdc_reply(dtdc_scan("ZZNEW", "Something", "14102026", "1000")), resolve)
        self.assertEqual(new.status, st.IN_TRANSIT)
        self.assertIn("ZZNEW", resolve.unknown)

    def test_not_found(self):
        result = dtdc.parse_tracking("D5", {"statusCode": 400, "errorDetails": "x"}, dtdc_resolver())
        self.assertFalse(result.found)

    def test_test_booking_is_marked(self):
        address = Address(name="A", line1="L1", pincode="110001")
        request = ShipmentRequest(reference="CTRACK1", service_code="PRIORITY", origin=address, destination=address,
                                  packages=[Package(weight=1.5)], declared_value=100, test_marking=True)
        body = dtdc.booking_json(request, "C1")["consignments"][0]
        self.assertEqual(body["customer_reference_number"], "TEST-RIGPL-CTRACK1")
        self.assertIn("TEST", body["description"])
        self.assertEqual((body["num_pieces"], body["weight"]), (1, 1.5))
        request.test_marking = False
        self.assertEqual(dtdc.booking_json(request, "C1")["consignments"][0]["customer_reference_number"], "CTRACK1")


class TestShipway(FrappeTestCase):
    def test_parse(self):
        provider = shipway.Shipway(Account(name="Shipway", provider="Shipway"))
        reply = {"status": "Success", "response": {"current_status_code": "DEL", "pickupdate": "2026-10-01 10:00:00",
                                                   "time": "2026-10-03 12:00:00", "to": "PUNE", "recipient": "R",
                                                   "scan": [{"time": "2026-10-02 08:00:00", "location": "HUB",
                                                             "status_detail": "In transit"}]}}
        result = shipway.parse_tracking("S1", reply, provider.resolve)
        self.assertEqual((result.status, result.destination, len(result.scans)), (st.DELIVERED, "PUNE", 1))
        self.assertEqual(result.delivery_date_time, datetime(2026, 10, 3, 12, 0))
        self.assertFalse(shipway.parse_tracking("S2", {"status": "Failed"}, provider.resolve).found)


class TestSeedRules(FrappeTestCase):
    def test_every_seed_row_is_valid_and_unique(self):
        self.assertEqual(set(SEED_RULES), {"DTDC", "Shipway", "FedEx"})
        for provider, rules in SEED_RULES.items():
            keys = [(m, c.upper()) for m, c, _s, _d in rules]
            self.assertEqual(len(keys), len(set(keys)), provider)
            for match_on, code, status, _description in rules:
                self.assertIn(match_on, (CODE, STARTS_WITH, TEXT), (provider, code))
                self.assertIn(status, st.ALL_STATUSES, (provider, code))

    def test_fedex_codes(self):
        resolve = StatusResolver("FedEx", rules=seed_rules("FedEx", SEED_RULES["FedEx"]))
        self.assertEqual(resolve("DL"), st.DELIVERED)
        self.assertEqual(resolve("OD"), st.OUT_FOR_DELIVERY)
        self.assertEqual(resolve("RS"), st.RTO)
        self.assertEqual(resolve("ZZ", "Delivery exception"), st.EXCEPTION)
