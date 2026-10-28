# Website (website_rigpl)

The Frappe v13 website for rigpl.com. It extends ERPNext Website Item through the `update_website_context` hook, with no separate product DocTypes. Data comes from Website Item (published, variant_of).

- `catalog.py`, `product_listing.py`, `item_page.py`, `product_info.py`, `cart.py`: catalog and pages.
- `routes.py`, `route_sync.py`, `legacy_routes.py`: URL rules (max 75 chars, shared routes).
- `item_sync.py`, `sales_rank.py`, `website_data/`: sync from Item, the ranking cron, the v12 data import.
- Table styles live in the Website Theme `rigpl-v12` Custom SCSS, not in app SCSS. It compiles with Node 14 only. Theme style changes go in the one patch `update_table_styles_in_website_theme`.

`website_rigpl/README.md` is large (33k). Open only the section you need:
§1 v12 changes · §2 web templates · §3 v12 import · §4 theme · §5 v13 vs v12 · §6 template pages · §7 open items.

Issues: epic #93 (label `website`). SEO meta and JSON-LD (#91) belong to the separate SEO-ECOMM project (WordPress). Do not write Frappe code for it.
