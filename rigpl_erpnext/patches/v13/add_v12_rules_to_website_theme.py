import frappe

from rigpl_erpnext.patches.v13.update_table_styles_in_website_theme import SECTION_MARKER as TABLES_MARKER
from rigpl_erpnext.patches.v13.update_table_styles_in_website_theme import save_custom_scss
from rigpl_erpnext.website_rigpl.website_data.importer import load_json, read_data_file

V12_RULES_MARKER = "// RIGPL v12 rules"


def execute():
    """
    Add the other v12 theme rules to the Custom SCSS of a theme that the import made before
    the rules were in the seed (#211). A new import gets them from the seed. Do not change a
    theme that has the rules already, so edits in Desk stay.
    """
    seed = load_json("theme")
    theme_name = seed["theme"]["theme"]
    if not frappe.db.exists("Website Theme", theme_name):
        print(f"Website Theme {theme_name} does not exist. The website import adds the v12 rules.")
        return

    current = frappe.db.get_value("Website Theme", theme_name, "custom_scss") or ""
    if V12_RULES_MARKER in current:
        return

    scss = read_data_file(seed["custom_scss_file"])
    rules = scss[scss.index(V12_RULES_MARKER) : scss.index(TABLES_MARKER)]
    save_custom_scss(theme_name, insert_before_tables(current, rules))


def insert_before_tables(current: str, rules: str) -> str:
    if TABLES_MARKER not in current:
        return current.rstrip("\n") + "\n\n" + rules
    start = current.index(TABLES_MARKER)
    return current[:start] + rules + current[start:]
