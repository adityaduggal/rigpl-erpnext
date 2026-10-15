import hashlib

import frappe

from rigpl_erpnext.website_rigpl.website_data.importer import load_json, read_data_file

SECTION_MARKER = "// RIGPL tables"  # prefix of every version of the section
V2_MARKER = "// RIGPL tables v2 (#95)"
V3_MARKER = "// RIGPL tables v3 (#108)"
# sha256 of the v2 section exactly as update_table_styles_in_website_theme wrote it
V2_SHA256 = "23909344b100c9d3ec90949c601c9940f38947b9a18b603fe2412b9255f4e919"


def execute():
    """
    Replace the v2 table styles in the Website Theme with v3: shop columns, headings that
    wrap, common specs in the variant table look and the description font (#108). The theme
    in the database is the source, so the patch replaces the section only when nobody
    edited it. Idempotent.
    """
    seed = load_json("theme")
    theme_name = seed["theme"]["theme"]
    if not frappe.db.exists("Website Theme", theme_name):
        return

    theme = frappe.get_doc("Website Theme", theme_name)
    current = theme.custom_scss or ""
    if V3_MARKER in current or V2_MARKER not in current:
        return

    start = current.index(V2_MARKER)
    if hashlib.sha256(current[start:].encode()).hexdigest() != V2_SHA256:
        print(
            f"Website Theme {theme_name}: the RIGPL tables section was edited in Desk, so it was not "
            "replaced. Copy the section '// RIGPL tables v3' from website_data/rigpl_v12_theme.scss "
            "into Custom SCSS by hand."
        )
        return

    scss = read_data_file(seed["custom_scss_file"])
    theme.custom_scss = current[:start] + scss[scss.index(SECTION_MARKER):]
    theme.save()  # validate() compiles the SCSS and throws on an error
    print(f"Website Theme {theme_name}: the RIGPL tables styles were updated to v3.")
