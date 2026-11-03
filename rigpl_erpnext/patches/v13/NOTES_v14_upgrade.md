# v14 upgrade: remove the v13 pricing rule backport

In v13, `rigpl_erpnext` backports the ERPNext v14 pricing rule "Has Priority" fix
(upstream commit `97fdda8a7c`, PR #41516). ERPNext v14 has this fix as standard code.

Do these steps before you run `bench migrate` on v14:

1. Delete Custom Field `Pricing Rule-has_priority`. Keep the database column. v14 adds
   `has_priority` as a standard field. If the custom field is still there, sync fails with
   `UniqueFieldnameError`. Use the same method as
   `patches/v13/remove_lead_designation_custom_field.py`.
2. Remove `rigpl_erpnext/overrides/pricing_rule_utils.py`, its test
   `rigpl_erpnext/tests/test_pricing_rule_override.py`, and the `before_request` and
   `before_job` entries in `hooks.py`.
   (On ERPNext other than v13, the override does nothing and writes a warning to the
   `rigpl_erpnext` log.)
3. In `rigpl_erpnext/validations/pricing_rule.py`, remove `doc.has_priority = 1`. v14
   sets it in `PricingRule.validate_mandatory`.
4. Test again on a draft Sales Order:
   - SarjunTools + HR4XSQ00E77, Qty 1: 55% (`HSS_tools_SarjunTools`).
   - A Large Dealer at or above a valid MOV value: the MOV rule (priority 19).
   - A customer with no rule for the item group: 0% (guard rule).

# v15 upgrade: website and the webshop app (#82)

In v15, ERPNext moves the e-commerce code (Website Item, the cart, product listing,
E Commerce Settings) to the separate `webshop` app. The website code reaches all of
these functions through `rigpl_erpnext/website_rigpl/compat.py`. Do not import
`erpnext.e_commerce` or `webshop` directly anywhere else.

The webshop paths were written on v13 without the webshop app. Check them at the upgrade:

1. Install the `webshop` app before you run `bench migrate` on v15.
2. For each name in `compat.ECOMMERCE`, check that the `webshop.webshop...` module and
   function exist. Fix a wrong path in `compat.py` only.
3. In `hooks.py` `override_whitelisted_methods`, check the 3 `webshop.webshop...` keys
   against the paths that the webshop JS calls. When v13 and v14 are gone, remove the
   `erpnext.e_commerce...` keys.
4. In `rigpl_variant_table.html`, check the JS cart object (`webshop.webshop.shopping_cart`).
5. E Commerce Settings becomes Webshop Settings. Check the fields that `catalog.py`
   `get_shop_info` and `get_selling_price_list` read: `enabled`, `show_price`,
   `hide_price_for_guest`, `show_stock_availability`, `show_quantity_in_website`,
   `allow_items_not_in_stock`, `price_list`.
6. Webshop owns Website Item and the website fields of Item Group. Check that these still
   sync: `website_rigpl/custom/website_item.json` and the Item Group custom fields
   `website_slug`, `include_in_url`, `rigpl_sales_rank` (#100).
7. v14+ uses the `page_renderer` hook in place of the generator order in
   `frappe/website/router.py`. Check the template, category and variant routes, and the
   301 redirects (#97, #102).
8. Bootstrap 4 becomes Bootstrap 5. Check the Website Theme `rigpl-v12` custom SCSS.
9. Test again: template page with the variant table and add to cart, guest product info
   (capped stock), category page order, and Item save (`item_sync`).
