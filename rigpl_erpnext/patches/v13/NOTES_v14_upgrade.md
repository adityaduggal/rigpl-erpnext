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
