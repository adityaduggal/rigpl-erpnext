import importlib
import types
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from rigpl_erpnext.website_rigpl import compat
from rigpl_erpnext.website_rigpl.compat import ECOMMERCE, get_ecommerce

REAL_IMPORT = importlib.import_module


def import_without_erpnext_ecommerce(fake_modules):
    """An import_module that has no ERPNext e-commerce, and gives the fake webshop modules."""

    def fake_import(path, *args, **kwargs):
        if path in fake_modules:
            return fake_modules[path]
        if path.startswith(("erpnext.e_commerce", "erpnext.utilities.product", "webshop")):
            raise ModuleNotFoundError(f"No module named '{path}'", name=path)
        return REAL_IMPORT(path, *args, **kwargs)

    return fake_import


class TestWebsiteCompat(FrappeTestCase):
    def test_v13_gives_the_erpnext_functions(self):
        for name, candidates in ECOMMERCE.items():
            module_path, attr = candidates[0]
            with self.subTest(name=name):
                self.assertIs(get_ecommerce(name), getattr(REAL_IMPORT(module_path), attr))

    def test_webshop_path_used_when_erpnext_has_no_ecommerce(self):
        module_path, attr = ECOMMERCE["place_order"][1]
        webshop_place_order = object()
        fake = {module_path: types.SimpleNamespace(**{attr: webshop_place_order})}
        with patch.object(compat.importlib, "import_module", import_without_erpnext_ecommerce(fake)):
            self.assertIs(get_ecommerce("place_order"), webshop_place_order)

    def test_no_module_found_names_every_path(self):
        with patch.object(compat.importlib, "import_module", import_without_erpnext_ecommerce({})):
            with self.assertRaises(ImportError) as ctx:
                get_ecommerce("make_website_item")
        for module_path, _attr in ECOMMERCE["make_website_item"]:
            self.assertIn(module_path, str(ctx.exception))

    def test_error_inside_a_module_is_not_hidden(self):
        def broken_import(path, *args, **kwargs):
            raise ModuleNotFoundError("No module named 'some_dependency'", name="some_dependency")

        with patch.object(compat.importlib, "import_module", broken_import):
            with self.assertRaises(ModuleNotFoundError) as ctx:
                get_ecommerce("place_order")
        self.assertEqual(ctx.exception.name, "some_dependency")

    def test_unknown_name_raises(self):
        with self.assertRaises(KeyError):
            get_ecommerce("not_an_ecommerce_function")

    def test_hooks_override_erpnext_and_webshop_paths_alike(self):
        overrides = frappe.get_hooks("override_whitelisted_methods")
        for name in ("place_order", "get_product_info_for_website", "get_product_filter_data"):
            erpnext_path, webshop_path = (f"{m}.{a}" for m, a in ECOMMERCE[name])
            with self.subTest(name=name):
                self.assertTrue(overrides.get(erpnext_path))
                self.assertEqual(overrides.get(webshop_path), overrides.get(erpnext_path))
