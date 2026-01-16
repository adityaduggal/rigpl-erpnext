__version__ = "14.0.0"

# Apply v16 report filter validation fix (makes ignore_link_validation work)
from rigpl_erpnext.patches.v16_report_fix import apply_report_patches
apply_report_patches()
