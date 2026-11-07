"""
Manual patch, not in patches.txt. The after_migrate hook import_website_once runs the import
one time on each site. Use this patch only to run it again:
    bench --site <site> run-patch --force rigpl_erpnext.patches.manual.import_website_data
See rigpl_erpnext/website_rigpl/README.md.
"""
from rigpl_erpnext.website_rigpl.website_data.importer import import_website


def execute():
    import_website()
