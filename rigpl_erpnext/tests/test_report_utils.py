from decimal import Decimal

from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.utils.report_utils import blank_zeros


class TestReportUtils(FrappeTestCase):
    def test_blank_zeros_keeps_text_dates_and_flags(self):
        row = ["CX0X", 0, 0.0, Decimal("0.000"), 2.5, "0", "-", False, None]

        self.assertEqual(blank_zeros(row), ["CX0X", None, None, None, 2.5, "0", "-", False, None])

    def test_blank_zeros_blanks_numbers_that_round_to_zero(self):
        row = [1e-10, -0.0004, 0.0006, Decimal("0.0001")]

        self.assertEqual(blank_zeros(row), [None, None, 0.0006, None])
        self.assertEqual(blank_zeros([0.4], precision=0), [None])
