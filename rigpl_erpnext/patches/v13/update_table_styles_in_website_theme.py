import hashlib

import frappe

from rigpl_erpnext.website_rigpl.website_data.importer import load_json, read_data_file

SECTION_MARKER = "// RIGPL tables"  # prefix of every version of the section
# sha256 of each earlier version of the section, exactly as a patch wrote it. A section with
# one of these hashes was not edited in Desk, so the patch can replace it.
UNEDITED_SHA256 = {
    "v1 (#95)": "aecc76bec82bcbe3225c38b58524aed877ea08916c0472b67723a1789c594af3",
    "v2 (#95)": "23909344b100c9d3ec90949c601c9940f38947b9a18b603fe2412b9255f4e919",
    "v3 (#108)": "36fd9bd3f89ff2b5d57c46c291237c4cb14be41c180d40108a270fd9450fab47",
}


def execute():
    """
    Put the newest RIGPL tables section of website_data/rigpl_v12_theme.scss into the
    Custom SCSS of the imported v12 Website Theme, so a website manager can change it in Desk.
    Add the section if it is not there. Replace it only when it is an earlier version that
    nobody edited. Idempotent. For a new section version, add its old hash to
    UNEDITED_SHA256 and a new #date to this patch in patches.txt.
    """
    seed = load_json("theme")
    theme_name = seed["theme"]["theme"]
    if not frappe.db.exists("Website Theme", theme_name):
        print(f"Website Theme {theme_name} does not exist. The website import adds the table styles.")
        return

    scss = read_data_file(seed["custom_scss_file"])
    newest = scss[scss.index(SECTION_MARKER):]
    current = frappe.db.get_value("Website Theme", theme_name, "custom_scss") or ""

    if SECTION_MARKER not in current:
        custom_scss = current.rstrip("\n") + "\n\n" + newest
    else:
        start = current.index(SECTION_MARKER)
        section = current[start:]
        if section == newest:
            return
        if hashlib.sha256(section.encode()).hexdigest() not in UNEDITED_SHA256.values():
            print(
                f"Website Theme {theme_name}: the RIGPL tables section was edited in Desk, so it was "
                "not replaced. Copy the newest section from website_data/rigpl_v12_theme.scss into "
                "Custom SCSS by hand."
            )
            return
        custom_scss = current[:start] + newest

    save_custom_scss(theme_name, custom_scss)


def save_custom_scss(theme_name: str, custom_scss: str):
    """Save and compile the theme. If node-sass cannot run (for example on a Node version
    that it does not support), keep only the SCSS, so the migrate does not stop. Do not try
    the compile then: Website Theme deletes the old CSS file before it compiles, so a failed
    compile leaves the site with no theme CSS.
    """
    if not can_compile_scss():
        frappe.db.set_value("Website Theme", theme_name, "custom_scss", custom_scss)
        print(
            f"Website Theme {theme_name}: the RIGPL tables styles were saved, but node-sass cannot "
            "run with this Node version, so the website still uses the old CSS. Use Node 14, then "
            "open the Website Theme in Desk and save it."
        )
        return

    theme = frappe.get_doc("Website Theme", theme_name)
    theme.custom_scss = custom_scss
    theme.save()  # validate() compiles the SCSS and throws on an error
    print(f"Website Theme {theme_name}: the RIGPL tables styles were updated. CSS: {theme.theme_url}")


def can_compile_scss() -> bool:
    """True if node-sass loads, which is what Website Theme uses to compile."""
    from subprocess import DEVNULL, run

    result = run(
        ["node", "-e", "require('node-sass')"],
        cwd=frappe.get_app_path("frappe", ".."),
        stdout=DEVNULL,
        stderr=DEVNULL,
    )
    return result.returncode == 0
