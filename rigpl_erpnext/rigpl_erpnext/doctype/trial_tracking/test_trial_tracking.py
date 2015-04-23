# Copyright (c) 2013, Rohit Industries Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('Trial Tracking')

class TestTrialTracking(unittest.TestCase):
	pass
