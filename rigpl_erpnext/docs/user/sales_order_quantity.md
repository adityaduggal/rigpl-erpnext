# Pack Size and Minimum Order Value Guide

The system checks the quantity of each item on a Sales Order and a Quotation. It checks the **Pack Size** and the **Minimum Order Value** (MoV). Click a section to open it.

## Which items are checked

The system checks an item only if both statements are true:

- The item is a variant of an item template.
- The item is not **Made to Order**.

The system does not check other items.

## Pack Size

The quantity must be a multiple of the **Pack Size** of the item. The Pack Size is a field of the Item. A Pack Size of `0` counts as `1`.

| Pack Size | Quantity | Result | Suggested quantity |
|---|---|---|---|
| 10 | 20 | Correct | None |
| 10 | 15 | Wrong | 20 |
| 10 | 5 | Wrong | 10 |

The suggested quantity is the next multiple of the Pack Size.

## Minimum Order Value

The **Selling MoV** field of the Item gives the minimum value of one row. The system compares it with the net amount of the row in the company currency.

The system shows a message only if both statements are true:

- The quantity of the row is more than the quantity available for sale.
- The net amount of the row is less than the Selling MoV.

A row that the available stock covers can be below the Selling MoV.

The message gives a suggested quantity. It is the smallest multiple of the Pack Size with a value of at least the Selling MoV.

| Selling MoV | Rate | Pack Size | Packs needed | Suggested quantity |
|---|---|---|---|---|
| 5000 | 30 | 20 | 8.33, so 9 | 180 |
| 4800 | 30 | 20 | 8 | 160 |

Packs needed is the Selling MoV divided by the value of one pack. The value of one pack is the rate multiplied by the Pack Size. The system rounds a part of a pack up to a full pack.

## Quantity available for sale

The system adds these quantities of the item:

- Planned quantity
- Stock in Finished Stock, Work In Progress, Raw Material and Dead Stock warehouses

Then it subtracts these quantities:

- Quantity reserved for Sales Orders
- Quantity reserved for production

A submitted Sales Order reserves stock. Because of this, the available quantity at submit can be lower than at save.

## When the system warns and when it stops you

A **warning** shows a message, and the document is saved or submitted. A **stop** shows a message, and the document is not saved or submitted.

| Action | Pack Size | Minimum Order Value |
|---|---|---|
| Save a Sales Order | Warning | Warning |
| Submit a Sales Order | Stop | Stop |
| Save a Quotation | Stop | Warning |
| Submit a Quotation | Stop | Warning |

A user with the **System Manager** role or the **Credit Controller** role gets a warning in all these cases. **Accounts Settings** sets the Credit Controller role.

When you submit, the Pack Size check runs first. If it stops you, correct the quantity and submit again. The MoV check can then show a second message.

## What to do when you see the message

1. Read the row number and the item code in the message.
2. Close the message.
3. Change the quantity of that row to a correct quantity.
4. For an MoV message, make sure that the net amount of the row is not less than the Selling MoV.
5. Save the document.

If the customer needs the quantity that the check stops, ask a System Manager or a Credit Controller to submit the document.
