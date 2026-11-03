import importlib
import pkgutil

from frappe.tests.utils import FrappeTestCase

import rigpl_erpnext


def get_module_names():
    for mod in pkgutil.walk_packages(rigpl_erpnext.__path__, "rigpl_erpnext."):
        yield mod.name


class TestModuleImports(FrappeTestCase):
    def test_every_module_imports(self):
        failed = []
        for name in get_module_names():
            try:
                importlib.import_module(name)
            except Exception as e:
                failed.append(f"{name}: {e!r}")
        self.assertEqual(failed, [], "\n".join(failed))
