import unittest
from decimal import Decimal

from rigpl_erpnext.utils.report_utils import blank_zeros


class TestReportUtils(unittest.TestCase):
    def test_blank_zeros_keeps_text_dates_and_flags(self):
        row = ["CX0X", 0, 0.0, Decimal("0.000"), 2.5, "0", "-", False, None]

        self.assertEqual(blank_zeros(row), ["CX0X", None, None, None, 2.5, "0", "-", False, None])
