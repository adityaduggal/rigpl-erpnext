# Rates on Delivery Note and Sales Invoice

The Sales Order is the only source of rates (#223).

- A Delivery Note or Sales Invoice row that comes from a Sales Order always has the rate, discount and price list rate of its Sales Order Item. This is the same if you pull the documents with "Get Items From" or make them with "Create".
- If a rate on the row is different, the system sets it back to the Sales Order rate when you save. A message names the changed rows.
- A Sales Invoice with only Sales Order rows gets "Ignore Pricing Rule" ticked. Pricing rules are not used for these rows.
- A Sales Invoice is blocked if the rate of a Delivery Note row is not the rate of its Sales Order row (for example SO 10 and DN 11). No role can bypass this. Correct or cancel the Delivery Note first.
- Rows without a Sales Order, and returns, are not changed.
