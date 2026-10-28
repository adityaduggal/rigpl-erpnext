import unittest

import frappe

from rigpl_erpnext.rigpl_erpnext.validations.pricing_rule import find_amount_band_errors

ITEM = "T42-Square HSS Tool Bits-BSW"


def band(name, min_amt, max_amt, priority="19"):
    return frappe._dict(name=name, item_code=ITEM, min_amt=min_amt, max_amt=max_amt, priority=priority)


class TestAmountBandValidation(unittest.TestCase):
    def test_joined_bands_pass(self):
        bands = [band("MOV58", 178571, 374999), band("MOV60", 375000, 0)]
        self.assertEqual(find_amount_band_errors(bands), [])

    def test_gap_between_bands(self):
        bands = [band("MOV60", 625000, 0), band("MOV58", 297620, 595236)]
        errors = find_amount_band_errors(bands)
        self.assertEqual(len(errors), 1)
        low, high, msg = errors[0]
        self.assertEqual((low, high), ("MOV58", "MOV60"))
        self.assertIn("MOV58 ends at 595,236 and MOV60 starts at 625,000", msg)
        self.assertIn("Set Max Amount of MOV58 to 624,999", msg)

    def test_open_band_below_another_band_overlaps(self):
        bands = [band("MOV58", 297620, 0), band("MOV60", 625000, 0)]
        errors = find_amount_band_errors(bands)
        self.assertEqual(len(errors), 1)
        self.assertIn("overlap", errors[0][2])

    def test_overlap_at_different_priority_passes(self):
        bands = [band("MOV58", 297620, 700000, "19"), band("MOV60", 625000, 0, "20")]
        self.assertEqual(find_amount_band_errors(bands), [])

    def test_single_or_open_top_band_passes(self):
        self.assertEqual(find_amount_band_errors([band("MOV60", 625000, 0)]), [])
        self.assertEqual(find_amount_band_errors([band("MOV58", 297620, 595236)]), [])
