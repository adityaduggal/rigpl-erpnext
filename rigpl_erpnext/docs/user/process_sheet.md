# How to use a Process Sheet

A Process Sheet is the production order for 1 item. It holds the operations, the raw material (RM) and the work in progress (WIP) items from a BOM Template. When you submit it, the system makes the Job Cards.

To make or change a BOM Template, see **Help > BOM Template Guide** on the BOM Template form.

## 1. Make a Process Sheet

1. Enter the **Production Item**.
   - For a variant item (made for stock), the Sales Order is optional.
   - For a made to order item (not a variant), enter the **Sales Order** and the Sales Order line. The item attributes come from the **Made to Order Item Attributes** of that line. If they are not submitted, the save stops and tells you to fill and submit them.
2. Save. The system:
   - selects the BOM Template (see section 2);
   - copies the operations and the warehouses of the template;
   - calculates the quantity (see section 3);
   - lists the RM and the WIP items (see sections 4 and 5).
3. Check the RM rows. Keep only the RM that you will use.
4. Submit.

Only 1 draft Process Sheet is allowed for each item (or for each item and Sales Order line).

## 2. BOM Template

- The system selects the first active template that matches the item. **Total Applicable BOM Templates** shows how many templates match.
- To use a different template, click **Select BOM Template Manually**. The list shows only the templates that match the item. You can search by the name, the title or the remarks.
- If the selected template is disabled, the save selects the first active template and shows a message. You cannot submit with a disabled template.

## 3. Quantity

- **Without a Sales Order:** the quantity is the **Minimum Qty to Manufacture**. It comes from the re-order level of the item, the lead time, the stock and the open documents.
- **With a Sales Order:** the quantity is the pending quantity of the Sales Order line.
- To enter a different quantity, tick **Update Qty Manually**. The system shows the calculated quantity as a message.
- The quantity cannot be more than **Maximum Qty to Manufacture**, unless the extra value is less than the limit in RIGPL Settings.
- An item with stock in Dead Stock cannot go into production.
- **Bypass all Qty Checks** stops these checks. Use it only with approval.

## 4. Select the RM

The RM table lists all RM items that pass the RM rules of the template.

- **Calculated Qty** is the RM quantity for the Process Sheet quantity, from the template formula. It is in the stock UOM of the RM: Nos for rods and pieces, Kg for RM by weight. It is rounded up to a whole number.
- **RM Cost** = Calculated Qty × Valuation Rate of the RM item.
- The rows are sorted by RM Cost. **The lowest cost is at the top.** RM with no valuation rate is at the bottom.
- RM with no stock (Qty Available = 0) is hidden. Tick **Show Unavailable RM** to see it.
- Click a row to see more: Projected Qty, Current Projected Qty, **Oldest Stock Age** and **Average Stock Age** (in days) of the RM in the source warehouse.
- Delete the rows that you will not use. On submit, the number of rows must be the **No of RM Items** of the template (usually 1).

How to select:

1. Use the first row that has enough stock for the Calculated Qty.
2. **TIP: use old stock.** If an RM a little lower in the list has stock older than **1 year (500 days)**, look at its RM Cost. If the cost difference is small, use the old stock, so that it does not become dead stock. If the old stock costs much more (for example 2 times or more), use the cheaper RM.

## 5. WIP items

- The **Item Manufactured** table lists the WIP items that the template makes from the selected RM.
- To get the WIP items again, clear the table and save.
- **Allow Zero ROL for WIP** also lists WIP items with no re-order level.

## 6. Submit and Job Cards

On submit:

- The system checks the RM rows (see section 4) and the quantity (it cannot be 0).
- It makes 1 Job Card for each open operation, if no open Job Card for the same item and operation exists. When a Job Card exists, the system updates its total quantity.

After submit:

- The status of the Process Sheet and of each operation changes when the Job Cards are completed: Submitted, In Progress, Completed, Short Closed.
- **Create New Job Card** on an operation row makes a Job Card for the pending quantity.
- **Stop Operation** on an operation row stops that operation and deletes its draft Job Cards.
- **Stop** stops the whole Process Sheet and deletes its draft Job Cards. **UnStop** starts it again and makes the missing Job Cards.
- Every 30 minutes, the manufacturing pipeline:
  1. makes the new Process Sheets;
  2. joins the transfer operations;
  3. cleans up the Job Cards;
  4. updates the Job Card status;
  5. updates the Process Sheet priority.

## 7. Troubleshooting

| Message | What to do |
|---|---|
| No BOM Template Found | No active template matches the item. Check the item attributes, or ask for a template (BOM Template Guide). |
| ... seems like a Special Item hence Sales Order is Mandatory | Enter the Sales Order and the Sales Order line. |
| Special Item Attributes not Submitted | Open the Made to Order Item Attributes in the message, fill them and submit. Then save again. |
| NO Raw Material Found | Tick Show Unavailable RM, change the RM warehouse, or select another template. |
| There are N Qty in Dead Stock | Use the dead stock first, or ask for Bypass all Qty Checks. |
| Max Qty Allowed to Manufacture = N | Reduce the quantity, or ask for Bypass all Qty Checks. |
| No of Allowed RM Items = N but Selected RM = M | Delete the RM rows that you will not use. Keep N rows. |
| Raw Material Consumption is Required | The template uses RM. Keep the RM rows. |
| Not Allowed to Submit Quantity Equal to ZERO | Enter a quantity, or do not submit. |
| Another Process Sheet with Same Item in Draft | Open the draft in the message and use it, or delete it. |
| BOM Template ... is disabled | The save selected another template. Check the new RM and WIP rows and save again. |
