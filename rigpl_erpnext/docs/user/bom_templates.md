# How to make a BOM Template

## 1. What a BOM Template does

A BOM Template (BOM Template RIGPL) tells the Process Sheet how to make a group of items:

- which finished items (FG) it applies to;
- which raw material (RM) to use;
- which work in progress (WIP) items to make;
- which operations to do, in which order, and in which warehouses;
- how much RM to use for the FG quantity.

**1 template for each process.** A template covers all the items that are made in the same way, from the same kind of RM, with the same operations. For example, Ball Nose and End Mills of any Carbide grade that are made from Round Tool Bits can use 1 template. Do not make a template for each grade, coating or tool type. Before you make a new template, find the templates that do the same work, and add the new values to one of them (see section 9).

## 2. How the Process Sheet selects a template

1. The Process Sheet reads the attributes of the production item. For a made to order item, it reads the Made to Order Item Attributes (see section 6).
2. A template matches when its Finished Item Restrictions are true for the item: each attribute of the rules (rows of the same attribute are OR, see section 3), and each numeric rule.
3. Only active templates match. A disabled template never matches.
4. When more than one template matches, the order is:
   1. the higher **Priority**;
   2. the template that this item used most in the submitted Process Sheets of the last 2 years;
   3. the template name.
5. The Process Sheet takes the first template. "Total Applicable BOM Templates" shows the number of templates that match.
6. To use a different template, click **Select BOM Template Manually** on the Process Sheet. The list shows only the templates that match the item. You can search by the template name, the title or the remarks.
   - **Why not other templates?** in that dialog (or **Help > BOM Template Match**) shows each template of the item's Base Material and Tool Type, and the rule that it fails. For example: "Carbide Quality = C-0X, allowed: C-1X, C-3X".
7. If the selected template is disabled, the save selects the first active template and shows a message. You cannot submit a Process Sheet with a disabled template.

## 3. Rules

A template has 3 rule tables:

| Table | Applies to | Names you can use in a numeric rule |
|---|---|---|
| Finished Item Restrictions | the production item | `fg_` |
| Raw Material Restriction | the RM items | `fg_`, `rm_` |
| Work In Progress Restrictions | the WIP items | `fg_`, `rm_`, `wip_` |

### How the rows work together

- **Rows of the same attribute are OR.** The item value must be one of the values of these rows.
- **Different attributes are AND.** Each attribute must pass.
- **Numeric rules are AND.** Each numeric rule must be true.

Example of FG rules for 1 Carbide process:

| Attribute | Allowed Values |
|---|---|
| Base Material | Carbide |
| Tool Type | Flat End Mills |
| Tool Type | Ball Nose End Mills |
| Carbide Quality | C-1X |
| Carbide Quality | C-3X |
| Carbide Quality | C-4X |
| d1_mm (numeric) | `fg_d1_mm > 2.5` |

The template matches a Carbide item that is a Flat End Mill **or** a Ball Nose End Mill, in C-1X **or** C-3X **or** C-4X, with d1 more than 2.5.

### Text rules

- Select the attribute and enter the allowed value, for example Base Material = Carbide.
- To allow more than 1 value, add more rows of the same attribute, or enter 1 value on each line in 1 row. Both work in the same way.
- In the RM and WIP tables, the value **No** means that the attribute is not checked. In the FG table, No is an ordinary value.
- **Value Source** (RM and WIP tables) takes the value from another item. Then Allowed Values is not used, and it must be the only row of its attribute:
  - **Same as FG**: the value must be the FG value of the same attribute. Example: RM Carbide Quality, Same as FG. An FG of C-3X uses an RM of C-3X.
  - **Same as RM** (WIP table only): the value must be the RM value of the same attribute. Example: WIP Carbide Quality, Same as RM.
- WIP that follows the FG and WIP that follows the RM are 2 different processes. Make 2 templates for them, even when the operations are the same.

### FG to RM Map

Use it when the RM value depends on the FG value, and it is not the same value. The map **defines** the RM values of its RM attributes. Each row has:

| FG Attribute | FG Value | RM Attribute | RM Values |
|---|---|---|---|
| Carbide Quality | C-0X | Carbide Quality | RC-ZF45 |
| Carbide Quality | C-3X | Carbide Quality | C-3X, RC-XF1, RC-TCHE, RC-TCST, RC-H10F (1 on each line) |
| Carbide Quality | C-4X | Carbide Quality | C-4X, RC-DM80, RC-K50U, RC-PN90 (1 on each line) |

- An RM attribute in the map must **not** have rows in the Raw Material Restriction table. The save stops if it has.
- Each FG value that the FG rules allow needs a map row. The save lists the missing values. Without a map row, no RM is found for those items.
- Use 1 FG attribute for each RM attribute. Only 1 row is allowed for each FG Attribute, FG Value and RM Attribute.
- For WIP, use Same as FG or Same as RM.

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
- **Operation Condition** (open the operation row): the Process Sheet uses the operation only for some FG values.
  - Set **Condition Attribute** (a text attribute of the FG), **Condition Type** (In or Not In) and **Condition Values** (1 on each line).
  - Example: Coating, Special Treatment, **Not In**, None. An FG with Special Treatment = None gets no Coating operation.
  - The operation that consumes the RM and the final operation cannot have a condition.
  - With no condition, the operation is always used.
- **Scrap** (open the operation row): the scrap that the operation makes, as an estimate. Set **Scrap Item**, **Scrap Qty Formula** and **Scrap Warehouse** (all 3, or none).
  - Example: ROD Cutting makes Carbide Solid Scrap; CNC Grinding makes Carbide Sludge Scrap; Marking makes no scrap (leave it empty).
  - 1 scrap item for each operation. A small scrap that is not worth tracking (for example the sludge of ROD Cutting) is left out.
  - The formula gives the scrap qty in the stock UOM of the scrap item (usually Kg). It can use `qty` (completed + rejected), `rm_qty` (RM used), `wip_qty`, `fg_`, `rm_`, `wip_` attributes and the renamed fields, for example `rm_oal`.
  - Example (Kg of rod cut-off): `rm_qty * (rm_oal - fg_oal * int(rm_oal / fg_oal)) * rm_d1_mm * rm_d1_mm * 0.0000123`.
  - The Job Card of the operation shows the **Estimated Scrap** (read only). On submit, its Stock Entry receives the scrap into the Scrap Warehouse at the valuation rate of the scrap item. Nobody enters it.

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

Make a new template only when the **process** is different: different operations, a different kind of RM, different numeric RM or WIP rules, WIP from the FG against WIP from the RM, or a different formula. A different grade, coating, purpose or tool type is not a different process.

When the work is the same and only the FG values are different, add the values to the existing template:

- Example: BT0000027, BT0000100, BT0000174 and BT0000269 are all Flat End Mill templates with the same operations (ROD Cutting > CNC Grinding > Coating > Marking). Only the FG Carbide Quality, Purpose or Special Treatment is different.
- Make 1 template, and add all the values in the FG rows (more rows of the same attribute, or 1 value on each line).
- Example: the H-1X Rectangular Tool Bit templates that do the same work become 1 template with all their FG values.
- When the RM grade changes with the FG grade, use **Same as FG** on the RM row, or the **FG to RM Map** (section 3). For WIP, use **Same as FG** or **Same as RM**.
- When an operation is only for some FG values (for example Coating only when Special Treatment is not None), give it an **Operation Condition** (section 5). Then the templates with and without Coating can be 1 template.
- Disable the old templates. Do not delete them, because old Process Sheets use them.

### Find and disable the templates that can merge

1. Open the report **BOM Template Overlaps**. **Match Level**:
   - **Exact**: the same work. Only the FG values (and the RM/WIP values) differ.
   - **Almost**: only the numbers in the rules differ, for example `+ 0.5` and `+ 1.5`.
   - **Same Operations**: the same operations, No of RM Items and Length Formula. This is the process view.
   Each group lists its templates, their FG values (what the merged template must hold), the Process Sheets of the last 2 years and the differences from the first template.
2. Make or change 1 template so that it holds all the FG values of the group (section 3).
3. On that template, click **Disable Similar Templates**. The dialog lists the active templates with the same operations, closest first (Exact, Almost, Similar), with:
   - the rule differences;
   - the **merge check**: the system takes up to 20 items of the Process Sheets of the last 2 years of each old template, and checks that this template gives them the same operations, RM sizes and WIP sizes. "0 differ" means it is safe.
4. Tick the templates to replace, and click **Disable Selected**. If a ticked template has differences, the system asks you to confirm. Each ticked template is disabled, gets **Merged Into** = this template, and a comment with your name.
5. A Process Sheet on a disabled template shows the template that replaces it.

## 10. Checklist before you save

- [ ] No active template already does this work (use the BOM Templates report).
- [ ] The FG rules match only the items you want. Use multi-value rows, not new templates.
- [ ] The RM and WIP rules use the correct prefixes (`fg_`, `rm_`, `wip_`).
- [ ] Each FG value of a mapped FG attribute has a row in the FG to RM Map, and the mapped RM attributes have no rows in the RM rules.
- [ ] Help > BOM Template Match on a Process Sheet shows the template as matched for 1 item of each old template.
- [ ] With Length Formula, each table has exactly 1 `oal` row.
- [ ] The formula gives the RM quantity for `qty` FG pieces.
- [ ] No of RM Items is correct.
- [ ] The Routing is set, and each operation has its warehouses. The last operation has a Final Warehouse.
- [ ] Priority is 0, unless this template must come before others.
