"""
Manual patch, not in patches.txt. Run it once per site:
    bench --site <site> run-patch rigpl_erpnext.patches.manual.import_website_data
See rigpl_erpnext/website_rigpl/README.md.
"""
from rigpl_erpnext.website_rigpl.website_data.importer import (
    import_home_page,
    import_theme,
    load_json,
    set_default_theme,
    set_home_page,
)


def execute():
    theme_seed = load_json("theme")
    import_theme(theme_seed)
    set_default_theme(theme_seed["theme"]["theme"])

    home_seed = load_json("home")
    import_home_page(home_seed)
    set_home_page(home_seed["route"])
