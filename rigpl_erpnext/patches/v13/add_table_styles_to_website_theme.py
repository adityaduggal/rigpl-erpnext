import frappe

from rigpl_erpnext.website_rigpl.website_data.importer import load_json, read_data_file

SECTION_MARKER = "// RIGPL tables"  # prefix of every version of the section


def execute():
    """
    Append the variant table styles (#95) to the Custom SCSS of the imported v12 Website
    Theme. The import copies the SCSS file only once, so a theme that exists now does not
    have them. Idempotent: the section marker shows that the styles are already there.
    """
    seed = load_json("theme")
    theme_name = seed["theme"]["theme"]
    if not frappe.db.exists("Website Theme", theme_name):
        print(f"Website Theme {theme_name} does not exist. The website import adds the table styles.")
        return

    theme = frappe.get_doc("Website Theme", theme_name)
    if SECTION_MARKER in (theme.custom_scss or ""):
        return

    scss = read_data_file(seed["custom_scss_file"])
    section = scss[scss.index(SECTION_MARKER):]
    theme.custom_scss = (theme.custom_scss or "").rstrip("\n") + "\n\n" + section
    theme.save()  # validate() compiles the SCSS and throws on an error
    print(f"Website Theme {theme_name}: the table styles were added to Custom SCSS.")
