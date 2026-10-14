"""
Manual patch, not in patches.txt. Run it to stop the website import message on
migrate without importing anything:
    bench --site <site> run-patch rigpl_erpnext.patches.manual.skip_website_data_import
"""


def execute():
    # The Patch Log entry that run-patch writes is the only effect.
    pass
