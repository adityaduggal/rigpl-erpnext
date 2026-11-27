# RIGPL Settings Guide

**RIGPL Settings** has the values that control RIGPL checks and scheduled jobs. This guide is for a System Manager. Click a section to open it. There is one section for each field.

## Raw Material check on Job Cards: when a bypass is needed

When a Job Card that consumes Raw Material (RM) is submitted, the system checks each RM row.

- **Made** = Total Completed Qty + Total Rejected Qty.
- **Difference** = the RM Qty minus the Calculated Qty, over or under.
- **Rate** = the Valuation Rate of the RM Item.
- **Value limit** = the higher of **Min RM Excess Value** and **RM Excess %** of (Calculated Qty x Rate), but not more than **RM Max Difference Value**.

A row needs **Bypass Qty Check** in these cases:

| Case | Bypass |
|---|---|
| Nothing made, RM Qty 0 | No |
| Nothing made, RM Qty above 0 | Yes |
| Something made, RM Qty 0 | Yes |
| Calculated Qty 0, RM Qty above 0 | Yes |
| Difference above **RM Max Qty Difference %** of the Calculated Qty | Yes |
| Difference x Rate above the value limit | Yes |
| All other rows | No |

An RM with Rate 0 has no value limit. The other cases apply to it.

A Job Card that consumes RM, made something, and has no RM row cannot be submitted.

Each row needs its own tick. Only a System Manager can tick **Bypass Qty Check**. With the tick, the system shows a warning and submits the Job Card. Use it, for example, when the RM was consumed with a separate Stock Entry.

### Examples

These examples use the limits 3,000, 5%, 20% and 25,000, and a Rate of 1,000.

| Calculated Qty | RM Qty | Difference value | Value limit | Result |
|---|---|---|---|---|
| 10 | 0 | 10,000 | 3,000 | Bypass: no RM |
| 10 | 8 | 2,000 | 3,000 | Allowed |
| 10 | 7 | 3,000 | 3,000 | Bypass: 30% |
| 100 | 95 | 5,000 | 5,000 | Allowed |
| 100 | 94 | 6,000 | 5,000 | Bypass: value |
| 100 | 106 | 6,000 | 5,000 | Bypass: value |
| 1000 | 975 | 25,000 | 25,000 | Allowed |
| 1000 | 970 | 30,000 | 25,000 | Bypass: value |

With a Rate of 100 and a Calculated Qty of 10, an RM Qty of 8 or 12 is allowed. An RM Qty of 39 needs a bypass, although its difference value is only 2,900.

The report **RM Wastage Analysis** applies the same check to submitted Job Cards. It uses the real cost of the RM from the Stock Ledger, and the limits of today.

## Manufacturing: Future Time Mins

How many minutes in the future the **To Time** of a Job Card time log can be. The system uses it only when the overlap check applies. With `0` or empty, a To Time after the present time is not allowed.

## Manufacturing: Check Overlap for Machines

When ticked, the time log checks apply to the Job Cards of all operations. When not ticked, they apply only to operations that have their own **Check Overlap for Machines** tick.

The checks need an Employee, a Workstation, From Time and To Time. Time logs must not overlap, and a row cannot have a Completed Qty of 0. A Job Card with **Bypass Time Logs**, and a subcontracting operation, skip these checks.

## Manufacturing: RM Stock Age Step (Days)

A Process Sheet ranks its RM options by cost. Old stock gets a lower rate, so that it is used first. The rate gets the discount of **RM Rate Discount per Age Step** for each full step of this number of days in Average Stock Age. Empty or `0` means 100.

Example: with 100 days, stock of an average age of 250 days gets 2 discounts.

## Manufacturing: RM Rate Discount per Age Step

The discount on the RM Valuation Rate for each age step, only to rank the RM. It does not change any stock value. The default is 5%.

Example: with 5%, 2 steps lower a rate of 1,000 to 900.

## Manufacturing: Min RM Excess Value

The RM difference value that is always allowed by the value limit, over or under the Calculated Qty. The default is 3,000. The **RM Max Qty Difference %** still applies below this value.

## Manufacturing: RM Excess %

The allowed RM difference value as a percent of the calculated RM value (Calculated Qty x Rate). The system uses it when it is higher than **Min RM Excess Value**. The default is 5%.

Example: a calculated value of 2,00,000 gives a value limit of 10,000.

## Manufacturing: RM Max Qty Difference %

The largest allowed difference between the RM Qty and the Calculated Qty, as a percent of the Calculated Qty. It applies to all values. The default is 20%. It must be above 0 and not more than 100.

There is no rounding exception. With a Calculated Qty of 1, an RM Qty of 2 needs a bypass.

## Manufacturing: RM Max Difference Value

The largest value limit. A difference value above it always needs a bypass, also on a large Job Card. The default is 25,000. It cannot be less than **Min RM Excess Value**.

Example: a calculated value of 10,00,000 with a difference of 30,000 (3%) needs a bypass.

## Customer Rating: Years to Consider

The number of past years of sales that the Customer Rating uses. If empty, the rating job uses 5 years, and the sales rating for payment terms uses 2 years.

## Customer Rating: Minimum First Order

The Age Factor of a customer starts at the first submitted Sales Order with a Net Total above this value. Empty means 10,000.

## Customer Rating: Rating Divisor

The Customer Rating is the total rating points divided by this number, with a maximum of 100. Empty or `0` means 1.

## Customer Rating: Minimum Orders Per Month

When above `0`, one tenth of this number is subtracted from the rating points of a customer. A customer with no Sales Order in the period always gets 0 points.

## Customer Rating: Default Payment Terms for Zero Sales Rating

The Payment Terms Template for:

- a customer with a sales rating of 0 and no payment terms, on save;
- the credit check of a customer with no payment terms;
- the scheduled job that moves customers with a Customer Rating of 0 to these terms.

## Customer Rating: Base Annual Sales

The annual sales that give a customer the full Sales Factor. The system does not use it when **Base Annual Sales from Company Sales** is ticked. Empty means 1,00,000.

## Customer Rating: Base Annual Sales from Company Sales

When ticked, the base annual sales come from the company sales: the Net Total of the submitted Sales Invoices of the period, for one year, multiplied by **Base Annual Sales % of Company Sales**.

## Customer Rating: Base Annual Sales % of Company Sales

The percent of the annual company sales that a customer must buy to get the full Sales Factor. It is needed when **Base Annual Sales from Company Sales** is ticked.

## Customer Rating: Sales Weightage

The weight of the Sales Factor in the rating points. The Sales Factor is the annual sales of the customer as a percent of the base annual sales, with a maximum of 100. The 3 weightages must total 100.

## Customer Rating: Payment Weightage

The weight of the Payment Factor in the rating points. The Payment Factor comes from the average number of days that the customer takes to pay.

## Customer Rating: Age Weightage

The weight of the Age Factor in the rating points. The Age Factor is the time since the first order (see **Minimum First Order**) as a percent of the rating period, with a maximum of 100.

## Reorder Level: Auto Process Sheet Value

The scheduled job makes a Process Sheet when the quantity to manufacture x Valuation Rate is this value or more. Below it, the job makes a Process Sheet only if the open Sales Orders need more than the stock and the production in progress. Empty means 10,000.

## Reorder Level: ROL Multiplier

Pairs of `multiplier:value`, separated by commas, for example `5:1000, 2.5:2000, 2:2500`. If Re Order Level x Valuation Rate is not above the largest value, the system multiplies the Re Order Level by the multiplier of the pair with the largest value. Above the largest value, the Re Order Level does not change. The other pairs have no effect. Empty means the example.

## Reorder Level: Base ROL Multiplier

The quantity to manufacture covers the calculated Re Order Level x this number x (lead time in days / 30). Empty or `0` means 1.

## Reorder Level: Max Months for Manufacturing Qty

The maximum quantity to manufacture uses this number of times the quantity of **Base ROL Multiplier**. Empty or `0` means 3.

## Reorder Level: Max Value Over Max Qty Allowed

A Process Sheet can be above its maximum quantity only up to this value (excess quantity x Valuation Rate). Above it, the Process Sheet needs **Bypass all Qty Checks**. The check does not apply to items with a Valuation Rate of 1 or less.

## Reorder Level: Minimum ROL Value

A Re Order Level whose value (quantity x Valuation Rate) is not above this amount becomes 0, for items with a Valuation Rate. It also sets the smallest Re Order Quantity. Empty means 10,000. **ROL Value Percentages** must have a pair with this value.

## Reorder Level: Max ROL Fluctuation

The largest change in the value of a Re Order Level in one update. Empty means 1,00,000. No pair of **ROL Value Percentages** can give a larger change at its own value.

## Reorder Level: ROL Value Percentages

Pairs of `value:percent`, separated by commas. For an item with a Valuation Rate, the Re Order Level can change by the percent of the pair with the largest value that is not above its present Re Order Level value. Below all values, the change is 100%. A percent cannot be above 100.

## Reorder Level: ROL Qty Percentages

Pairs of `quantity:percent`, separated by commas. The same limit as **ROL Value Percentages**, by quantity, for items with no Valuation Rate. Pairs for the quantities `0` and `1` are needed.

## Reorder Level: ROL Calculation

Periods in months, separated by commas, for example `12,18,24`. They apply to items that are not sold, whose Re Order Level comes from purchases or consumption. Empty means `12,18,24,30,36`. The website sales rank uses the shortest period.

## Reorder Level: ROL Safety Factor

The safety stock factor for sales items that are ordered often. The Re Order Level is the demand in the lead time plus this factor x the variation of that demand. The default 1.65 gives about 95% of lead times without a stock-out.

## Reorder Level: ROL Consumption Safety Factor

The same factor for items whose Re Order Level comes from consumption with Stock Entries. The default is 1.

## Reorder Level: Big Order Multiple for ROL

An order line above this number of times the median order quantity of the item counts only up to that limit. One large order then does not raise the Re Order Level much. The default is 5.

## Reorder Level: Max Transactions for Lead Time to Consider

The lead time of an item uses only this number of its latest Purchase Orders or Process Sheets. Empty or `0` means 10.

## Website: Website Stock Cap

A stock quantity above this number shows as the **Website Stock Cap Label**. The website never shows the real quantity above the cap. Stock shows only when **E Commerce Settings > Show Stock Availability** is on. Empty means 100.

## Website: Website Stock Cap Label

The text for stock above the cap. `{cap}` is replaced with the cap. Empty means `{cap}+`.

## Website: Website Zero Stock Label

The text for an item with no stock. Empty means `On request`.

## Website: Website Route Max Length

The maximum number of characters in a website route. The system cuts a template name to fit. A change applies on the next save of an Item Group. Empty means 75.

## Website: Website Route Max Depth

The maximum number of Item Groups in a category route. **Item Group > Include in URL** selects the groups. Empty means 2.

## Shipping: Unpublish Days After Delivery

A tracking page is unpublished this number of days after delivery. Empty means 7.

## Shipping: Published Ctrack Days

A tracking page is unpublished this number of days after its creation, also when the shipment is not delivered. Empty means 90.

## Shipping: Auto Close Days

An open tracking older than this is polled one more time, then closed as **Closed - No Update**. Empty means 150.

## Shipping: Max Track Days (API)

Trackings of carriers with an API, older than this, are not polled. Empty means 150.

## Shipping: Max Track Days (Shipway)

Shipway trackings older than this are not polled. Empty means 60.

## Shipping: Poll Every (Hours)

The system polls an open tracking when its last update is older than this. Empty means 6.

## Shipping: Poll Every With Webhooks (Hours)

The same, for accounts with webhooks. Empty means 24.

## Shipping: Shipway Push Max Days

The system sends an AWB to Shipway only in this number of days. Empty means 20.

## Shipping: Sales Invoice Table for Carriers

The Sales Invoice table that carriers get as the customs lines: **Item Synopsis** or **Items**. Empty means Item Synopsis.

## HR: Loan Deduction Component

The Salary Component of a new loan (an Employee Advance that is repaid from the salary). Empty means **Loan Deduction**.

## HR: Department Approvers

On save of a Department, the system copies the Leave Approvers to the other approver tables that the option makes the same. Empty means **Leave, Expense and Shift Same**.
