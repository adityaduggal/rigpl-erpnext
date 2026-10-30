# How to make a BOM Template

## 1. What a BOM Template does

A BOM Template (BOM Template RIGPL) tells the Process Sheet how to make a group of items:

- which finished items (FG) it applies to;
- which raw material (RM) to use;
- which work in progress (WIP) items to make;
- which operations to do, in which order, and in which warehouses;
- how much RM to use for the FG quantity.

One template covers many items. Do not make a template for one item. Before you make a new template, find the templates that do the same work. Add the new values to one of them (see section 9).

## 2. How the Process Sheet selects a template

1. The Process Sheet reads the attributes of the production item. For a made to order item, it reads the Made to Order Item Attributes (see section 6).
2. A template matches when **all** of its Finished Item Restrictions are true for the item.
3. Only active templates match. A disabled template never matches.
4. When more than one template matches, the order is:
   1. the higher **Priority**;
   2. the template that this item used most in the submitted Process Sheets of the last 2 years;
   3. the template name.
5. The Process Sheet takes the first template. "Total Applicable BOM Templates" shows the number of templates that match.
6. To use a different template, click **Select BOM Template Manually** on the Process Sheet. The list shows only the templates that match the item. You can search by the template name, the title or the remarks.
7. If the selected template is disabled, the save selects the first active template and shows a message. You cannot submit a Process Sheet with a disabled template.

## 3. Rules

A template has 3 rule tables:

| Table | Applies to | Names you can use in a numeric rule |
|---|---|---|
| Finished Item Restrictions | the production item | `fg_` |
| Raw Material Restriction | the RM items | `fg_`, `rm_` |
| Work In Progress Restrictions | the WIP items | `fg_`, `rm_`, `wip_` |

### Text rules

- Select the attribute and enter the allowed value, for example Base Material = Carbide.
- To allow more than 1 value, enter 1 value on each line. For example, Carbide Quality:

  ```
  C-1X
  C-3X
  ```

  The rule is true when the item value is one of the lines.
- In the RM and WIP tables, the value **No** means that the attribute is not checked.

### Numeric rules

- Tick **Is Numeric** and enter the rule. Write the attribute name with its prefix, for example `fg_d1_mm`, `rm_l1_mm`.
- Use `==`, `!=`, `>`, `>=`, `<`, `<=`, `&&` (and), `||` (or), brackets, `+ - * /` and `ceiling()`.
- Example from BT0000027 (RM diameter):

  ```
  ( rm_d1_mm == fg_d2_mm || ( rm_d1_mm == fg_d2_mm + 1.5 ) )
  ```

- An RM item that does not have an attribute of the rule does not pass the rule.

### Length formula and the `oal` field

- Tick **Length Formula** when the RM is cut to length.
- In each rule table, mark the length attribute with **Rename Field** and the name `oal`. Only 1 row in each table can have `oal`.
- In BT0000027: FG `l2_mm`, RM `l1_mm` and WIP `l1_mm` are `oal`.
- The Job Card uses the `oal` fields to check the wastage of RM length.

## 4. Quantity formula and No of RM Items

- **Formula for Total Qty** gives the RM quantity for the FG quantity. Use `qty` (the FG quantity), `fg_`, `rm_` and the renamed fields.
- Example from BT0000027:

  ```
  int( qty / int( ( rm_oal + 6 ) / fg_oal ) )
  ```

  This gives the number of RM rods: each rod of length `rm_oal + 6` makes `int((rm_oal + 6) / fg_oal)` pieces.
- **No of RM Items** is the number of RM rows that the Process Sheet must have on submit. It is usually 1.

## 5. Operations

- **Routing** is mandatory. If the Operations table is empty, the save copies the operations of the Routing.
- For each operation, set:
  - **Allow Consumption of RM** and the **RM Warehouse**, for the operation that uses the RM;
  - **Allow Production of WIP Materials** and the **WIP Material Warehouse**, for the operation that makes WIP;
  - **Source Warehouse** and **Target Warehouse**, when the material moves between warehouses;
  - **Final Warehouse** on the last operation. The finished items go there.
- Rules for subcontracting operations:
  - It cannot be the first operation or the last operation.
  - It cannot consume RM.
  - Its target warehouse is the subcontracting warehouse of the Operation.
- Operation time and batch size can come from a formula. Tick the "based on formula" check and enter the formula.

Example, BT0000027: ROD Cutting (uses RM, makes WIP) > CNC Grinding > Coating (subcontracting) > Marking (final warehouse BGH655 - RIGPL).

## 6. Made to order items

- A made to order item is not a variant. Its attributes come from the Sales Order.
- A Process Sheet for this item needs the Sales Order.
- When no Made to Order Item Attributes exist for the Sales Order line, the system makes a draft. Fill in the attributes and submit it, then save the Process Sheet again.
- The template rules use these attributes in the same way as the attributes of a variant.

## 7. Quantity to make

The template does not set the quantity. The Process Sheet calculates it from the item:

- **Minimum Qty to Manufacture** comes from the calculated re-order level of the item, the lead time, and **Base ROL Multiplier** in RIGPL Settings, less the stock and the open documents.
- **Maximum Qty to Manufacture** uses **Max Months for Manufacturing Qty** in RIGPL Settings.
- A larger quantity is allowed only when the extra value is less than **Max Value Over Max Qty Allowed**.
- An item with dead stock cannot go into production.
- **Bypass all Qty Checks** stops these checks. Use it only with approval.
- For a Process Sheet with a Sales Order, the quantity is the pending quantity of the Sales Order line.

## 8. RM rows and cost

The Process Sheet sorts the RM rows by cost, with the lowest cost at the top. To select the RM, see **Help > Process Sheet Guide** on the Process Sheet form.

## 9. New template or new value?

Make a new template only when the work is different: different operations, different RM rules or WIP rules, or a different formula.

When the work is the same and only the FG values are different, add the values to the existing template:

- Example: BT0000027, BT0000100, BT0000174 and BT0000269 are all Flat End Mill templates with the same operations (ROD Cutting > CNC Grinding > Coating > Marking). Only the FG Carbide Quality, Purpose or Special Treatment is different.
- Make 1 template, and enter all the values, 1 on each line, in the FG rows.
- Disable the old templates. Do not delete them, because old Process Sheets use them.

## 10. Checklist before you save

- [ ] No active template already does this work (use the BOM Templates report).
- [ ] The FG rules match only the items you want. Use multi-value rows, not new templates.
- [ ] The RM and WIP rules use the correct prefixes (`fg_`, `rm_`, `wip_`).
- [ ] With Length Formula, each table has exactly 1 `oal` row.
- [ ] The formula gives the RM quantity for `qty` FG pieces.
- [ ] No of RM Items is correct.
- [ ] The Routing is set, and each operation has its warehouses. The last operation has a Final Warehouse.
- [ ] Priority is 0, unless this template must come before others.
