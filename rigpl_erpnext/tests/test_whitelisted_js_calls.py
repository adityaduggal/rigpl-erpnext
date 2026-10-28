import ast
import os
import re

from frappe.tests.utils import FrappeTestCase

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PARENT = os.path.dirname(APP_DIR)

# "method: 'a.b.c'", "query: 'a.b.c'" and "frm.call('x')" in the form scripts
CALL_RE = re.compile(r"""(?:method|query)\s*:\s*['"]([\w.]+)['"]|frm\.call\(\s*['"]([\w.]+)['"]""")
STRING_JOIN_RE = re.compile(r"""['"]\s*\+\s*\n?\s*['"]""")


def get_js_files():
    for root, dirs, files in os.walk(APP_DIR):
        dirs[:] = [d for d in dirs if d not in ("dist", "node_modules", "__pycache__")]
        for name in files:
            if name.endswith(".js"):
                yield os.path.join(root, name)


def get_whitelisted_functions(py_path):
    """
    Returns the names of the functions and methods in `py_path` with @frappe.whitelist()
    """
    with open(py_path) as f:
        tree = ast.parse(f.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(target, ast.Attribute) and target.attr == "whitelist":
                    names.add(node.name)
    return names


def get_called_methods(js_path):
    with open(js_path) as f:
        # Join "a." + "b" strings, as in the report filters
        text = STRING_JOIN_RE.sub("", f.read())
    for match in CALL_RE.finditer(text):
        yield match.group(1) or match.group(2)


class TestWhitelistedJsCalls(FrappeTestCase):
    def test_js_calls_are_whitelisted(self):
        errors = []
        for js_path in get_js_files():
            controller = js_path[:-3] + ".py"
            for method in get_called_methods(js_path):
                if "." in method:
                    if not method.startswith("rigpl_erpnext."):
                        continue
                    module, func = method.rsplit(".", 1)
                    py_path = os.path.join(APP_PARENT, *module.split(".")) + ".py"
                else:
                    # doc: frm.doc calls a method of the doctype controller
                    py_path, func = controller, method
                rel = os.path.relpath(js_path, APP_DIR)
                if not os.path.exists(py_path):
                    errors.append(f"{rel}: {method} (no file {os.path.relpath(py_path, APP_PARENT)})")
                elif func not in get_whitelisted_functions(py_path):
                    errors.append(f"{rel}: {method} is not whitelisted")
        self.assertEqual(errors, [], "\n".join(errors))
