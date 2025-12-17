import frappe

def get_website_route_rules():
    rules = []
    try:
        # Check if the Item Group table exists to avoid errors during installation
        if not frappe.db.exists("DocType", "Item Group"):
            return []

        top_level_groups = frappe.get_all(
            "Item Group",
            filters={"parent_item_group": ('in', ('', None, 'All Item Groups'))},
            fields=["custom_route", "name"]
        )
        
        for group in top_level_groups:
            route = group.custom_route or group.name
            if route:
                # Rule for any sub-paths (e.g., /category/sub-category, /category/item)
                rules.append({"from_route": f"/{route}/<path:path>", "to_route": "products"})
                # Rule for the group page itself (e.g., /category)
                rules.append({"from_route": f"/{route}", "to_route": "products"})

        frappe.log_error(title="Generated Website Route Rules", message=str(rules))

    except (frappe.db.TableMissingError, frappe.exceptions.DoesNotExistError):
        # This can happen during a fresh install/uninstall cycle when the DB is not ready.
        # It's safe to just return no rules in this case.
        pass
    except Exception as e:
        # Log any other unexpected errors
        frappe.log_error(f"Could not generate dynamic website route rules: {e}")

    return rules
