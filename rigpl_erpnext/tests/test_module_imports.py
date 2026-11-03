import importlib
import os
import pkgutil

from frappe.tests.utils import FrappeTestCase

import rigpl_erpnext

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL_PATCHES = "rigpl_erpnext.patches.manual_patches"

# Old patches already in Patch Log that fail for reasons not tied to v13 (#158)
KNOWN_BROKEN = {
    "rigpl_erpnext.patches.20160325_xss_removal",  # Python 2 HTMLParser
    "rigpl_erpnext.patches.item_master.remove_extra_images_from_items",  # gone from rohit_common
}


def get_module_names():
    for mod in pkgutil.walk_packages(rigpl_erpnext.__path__, "rigpl_erpnext."):
        yield mod.name
    # manual_patches has no __init__.py, so walk_packages skips it
    manual_dir = os.path.join(APP_DIR, "patches", "manual_patches")
    for name in sorted(os.listdir(manual_dir)):
        if name.endswith(".py"):
            yield f"{MANUAL_PATCHES}.{name[:-3]}"


class TestModuleImports(FrappeTestCase):
    def test_every_module_imports(self):
        failed = []
        for name in get_module_names():
            if name in KNOWN_BROKEN:
                continue
            try:
                importlib.import_module(name)
            except Exception as e:
                failed.append(f"{name}: {e!r}")
        self.assertEqual(failed, [], "\n".join(failed))
