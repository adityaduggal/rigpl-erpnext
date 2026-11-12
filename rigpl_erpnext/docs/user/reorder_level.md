# How the Re Order Level (ROL) is set

The ROL of an item is the stock level at which the system asks to order or make more of it. The job `auto_reorder` sets the ROL of all enabled variant items that are not made to order. It runs every quarter, on 1 January, April, July and October at 3:15 AM.

## What ROL means

ROL is a **quantity**, not a monthly value. For a sales item it is:

> demand in the lead time + safety stock

- **Demand in the lead time** is the average daily demand multiplied by the **Lead Time Days** of the item. If the item has no lead time, the system uses 30 days.
- **Safety stock** is the **ROL Safety Factor** of RIGPL Settings multiplied by the variation of the demand over the lead time. A factor of 1.65 covers about 95% of the lead times without a stock-out.
- The ROL from consumption (see below) is added.

The average daily demand comes from the Sales Orders of a number of months. The number of months depends on the order class of the item. A month is not a unit of the ROL.

## Order classes of sales items

The system counts the submitted Sales Orders and the customers of the last 12 months.

| Class | Orders in 12 months | Months of data | Demand bucket |
|---|---|---|---|
| Fast | 53 or more | 6 | 7 days |
| Regular | 13 or more | 12 | 7 days |
| Occasional | 4 or more | 24 | 30 days |
| Rare | all other items | 24 | not used |

An item with orders from 1 or 2 customers needs at least 13 orders in 12 months to be in Fast or Regular. With fewer orders it is **Rare**.

A single order counts only up to **Big Order Multiple for ROL** times the median order quantity, so one big order does not raise the ROL.

## Rare items have ROL 0

An item that is seldom ordered gets ROL 0. The system does not keep stock for it. When a customer orders it, you buy or make it for that order.

A Rare item keeps a ROL only when it has a ROL from consumption (next section).

A ROL of 0 is set at once. The change limits below do not apply to it.

## Consumption adds to the ROL

Items that are used to make other items have no Sales Orders, or only a few. For them the system also counts the quantity taken out with Stock Entries (source warehouse set, no target warehouse). The ROL from consumption is added to the ROL from sales.

The consumption counts only when the item has **more than 3 Stock Entries in the last 6 months, or more than 6 in the last 12 months**.

> average daily consumption x lead time + safety stock

- The average and the variation come from the consumption of the last 12 months in buckets of 7 days.
- The safety stock is the **ROL Consumption Safety Factor** of RIGPL Settings (1 if empty) multiplied by the variation of the weekly consumption over the lead time.

## Limits on a change

For the other classes, the new ROL cannot differ from the existing ROL by more than the rules of RIGPL Settings allow:

- **ROL Qty Percentages** and **ROL Value Percentages**: the percentage change allowed for the existing qty or value.
- **Max ROL Fluctuation**: the largest change in value.
- **Minimum ROL Value**: if ROL multiplied by the valuation rate is below this value, the ROL is 0.

Items that are not sold use their purchases or consumption in the periods of **ROL Calculation**.

## Check a change before it is saved

Run the job as a dry run. It saves nothing. It writes `rol_preview.csv` in the site folder with the old and new ROL of each item that would change:

```
bench --site <site> execute rigpl_erpnext.rigpl_erpnext.scheduled_tasks.auto_reorder.execute --kwargs '{"dry_run": 1}'
```

The **Basis** column shows the class and the months of data, and `+ Consumption` when consumption is added. A Rare item without consumption shows `Rare (...), no ROL`.

The dry run saves nothing. To apply the preview, run the same command without `--kwargs`, or wait for the next quarterly run.
