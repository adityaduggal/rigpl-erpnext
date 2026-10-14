import hashlib

import frappe

from rigpl_erpnext.website_rigpl.website_data.importer import load_json, read_data_file

V1_MARKER = "// RIGPL tables (#95)"
V2_MARKER = "// RIGPL tables v2 (#95)"
# sha256 of the v1 section exactly as add_table_styles_to_website_theme appended it
V1_SHA256 = "aecc76bec82bcbe3225c38b58524aed877ea08916c0472b67723a1789c594af3"


def execute():
    """
    Replace the v1 table styles in the Website Theme with v2: filter, column sort,
    floating header and phone cards (#95). The theme in the database is the source, so the
    patch replaces the section only when nobody edited it. Idempotent.
    """
    seed = load_json("theme")
    theme_name = seed["theme"]["theme"]
    if not frappe.db.exists("Website Theme", theme_name):
        return

    theme = frappe.get_doc("Website Theme", theme_name)
    current = theme.custom_scss or ""
    if V2_MARKER in current or V1_MARKER not in current:
        return

    start = current.index(V1_MARKER)
    if hashlib.sha256(current[start:].encode()).hexdigest() != V1_SHA256:
        print(
            f"Website Theme {theme_name}: the RIGPL tables section was edited in Desk, so it was not "
            "replaced. Copy the section '// RIGPL tables v2' from website_data/rigpl_v12_theme.scss "
            "into Custom SCSS by hand."
        )
        return

    scss = read_data_file(seed["custom_scss_file"])
    theme.custom_scss = current[:start] + scss[scss.index(V2_MARKER):]
    theme.save()  # validate() compiles the SCSS and throws on an error
    print(f"Website Theme {theme_name}: the RIGPL tables styles were updated to v2.")
