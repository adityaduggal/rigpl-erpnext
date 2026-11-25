# Carrier Tracking

A Carrier Tracking holds one shipment: the transporter, the AWB number, the packages, the status and the
scans from the carrier. The system makes a Carrier Tracking when you submit a Sales Invoice with a
tracked transporter. You can also make one by hand from the Carrier Tracking list.

Admins: see [Shipping Providers setup](../setup/shipping-providers.md).

## Book a shipment

1. Open the Carrier Tracking of the Sales Invoice.
2. Check the From Address, To Address and Contact Person.
3. Add a row in **Shipment Package Details** for each box. Enter the weight in Kg.
4. For a FedEx export, attach the invoice PDF in **Customs Invoice PDF** (see below).
5. Save.
6. Click **Shipment > Get Rates** to see the cost. This step is optional.
7. Click **Shipment > Book Shipment**.

The booking sets the AWB number, attaches the labels and submits the tracking. The AWB also goes to the
Sales Invoice.

### The invoice lines that the carrier gets

For a Sales Invoice, FedEx gets one customs line for each row of one table of the invoice. The customs value
of a line is the **Amount** of the row.

Select the table in **RIGPL Settings > Shipping > Sales Invoice Table for Carriers**:

| Value | Rows that go to the carrier |
|---|---|
| Item Synopsis (default, also when empty) | The summary for the customer. |
| Items | The item rows of the invoice. |

When the selected table has no rows, the system stops with a message. Add the rows, or change the setting.

### FedEx export: the customs documents

FedEx sends the customs documents to customs electronically (ETD). You attach them on the tracking before
you book.

1. Make the invoice PDF:
   - Purpose SOLD: the tax invoice of the Sales Invoice.
   - Any other purpose (sample, gift, catalogs, repair): a pro forma invoice.
2. Attach the PDF in **Customs Invoice PDF**.
3. Optional: attach one more document, for example a packing list, in **Other Trade Document**.
4. Save, then book.

The booking stops when the invoice PDF is missing, when it is not a PDF, or when a file is more than 5 MB.

The booking message tells you what to print:

| Booking message | Print |
|---|---|
| "Print N copies of the Customs Invoice PDF" | The labels, and N copies of the invoice PDF. Put the invoices in a pouch on the box. The label shows "EWO". |
| "No paper copy is needed" | The labels only. |

**FedEx ETD** shows the documents that FedEx took. **Invoice Copies to Print** keeps the number of copies.

The system deletes the two files from the tracking a day after delivery.

FedEx also gets the Item Code of each invoice line as the product id (`EU_DE_MINIMIS`, #242) when the
shipment goes to an EU country.

### Export clearance (CSB-IV, CSB-V, Shipping Bill)

When you save an export from India, **Export Clearance** shows how customs clears it:

| Export Clearance | When |
|---|---|
| CSB-V | Purpose SOLD and the Sales Invoice is Rs 10 lakh or less (Grand Total in INR). |
| Shipping Bill | Purpose SOLD and the Sales Invoice is more than Rs 10 lakh. The FedEx agent files a formal shipping bill. |
| CSB-IV | All other purposes: sample, gift, catalogs, repair and return. |

The field changes only while the tracking is a draft.

A FedEx booking sends one line to FedEx with the clearance, the IEC, the AD code, the GSTIN and the LUT. For
example: "CSB-V. IEC 0500000001. AD Code 01234560000001. GSTIN 06... Export under LUT ... without IGST."

For purpose SOLD, the booking stops when one of these is missing:

- **IEC Code**, **Bank AD Code** or **Export Type** in the Sales Taxes and Charges Template of the Sales Invoice.
- The GSTIN of the From Address.

FedEx has not yet confirmed which API fields it wants for CSB shipments (#241). The line goes in the
special instructions of the commercial invoice.

For a transporter with no booking API, type the AWB number from the carrier receipt, then submit.

## The Shipment menu

The **Shipment** menu is at the top of the form. It shows only the actions that apply to this tracking
now. The server checks the action again when you click it.

| Action | Shows when |
|---|---|
| Get Rates | The tracking is a draft and is not booked. The carrier has a rate API, or the transporter calculates the cost from its quote. |
| Book Shipment | The tracking is a draft and is not booked. The transporter has API Mode "Booking and Tracking". |
| Preview Request | Shows the calls that another action of this menu would send. System Managers and the users who can delete Carrier Tracking or set its user permissions only. Any status. The carrier must support it (FedEx, DTDC, Shipway). |
| Validate Address | The tracking is not booked. The carrier can check addresses (FedEx). |
| Available Services | The tracking is not booked. The carrier can check the pincode or route. |
| Get Label | The tracking has an AWB and is not picked up yet (status Booked or empty). The carrier gives labels (DTDC). |
| Get Status | The tracking has an AWB and its status is not final. |
| Post to Shipway | Shipway carriers only: the AWB is not sent to Shipway yet. |
| Get Proof of Delivery | The status is Delivered and no proof of delivery is attached. FedEx only. |
| Delete Shipment | The status is Booked (not picked up yet) and the transporter books by API. |

"Not booked" means: the tracking has no AWB, and the status is not Booked, In Transit, Out for
Delivery, Delivered or RTO.

**Delete Shipment** asks you to confirm. It cancels the AWB with the carrier and makes the tracking a
draft again with AWB "NA". You can then book it again. A carrier with no cancel API shows a message.
Cancel the AWB on the carrier portal in that case.

If the form has changes that are not saved, an action saves the form first. Preview Request does not save.

### Test without sending data to the carrier

Click **Preview Request**, pick an action (only the actions that apply to the tracking now are listed) and
click Preview. The window shows each call as `METHOD url` (the service that gets it) and the body. Nothing
goes to the carrier, and nothing is saved. Passwords, keys and tokens are not shown. A long file (the
invoice PDF) shows as a number of characters.

To stop every carrier call on a site (for example a dev copy), set `"shipping_block_calls": 1` in its
`site_config.json`. Get Rates, Book Shipment and the other actions then stop before the call and show the
body they would send. The secret keys are not shown. Remove the key on the production site.

Click **Help** at the top of the form to open this page.

## Statuses

| Status | Meaning |
|---|---|
| Booked | The carrier has the AWB. The shipment is not picked up yet. |
| In Transit | The carrier has the shipment. |
| Out for Delivery | The shipment is with the delivery agent. |
| Delivered | The receiver has the shipment. Final. |
| RTO | The shipment goes back to us. Final. |
| Exception | The carrier reports a problem, for example a wrong address. Call the carrier. |
| Cancelled | The shipment was cancelled. Final. |
| No Information | The carrier does not know the AWB yet. |
| Closed - No Update | The carrier gave no update for a long time and the admin closed the tracking. Final. |
| Not Booked | The booking was deleted. Final until you book again. |

The system does not ask the carrier about a tracking with a final status again.

## How the status changes

You do not need to click **Get Status**. Each hour, a job asks the carriers about the open trackings:

- A tracking is asked about again when its last update is more than 6 hours old.
- The job starts 2 days after the tracking is made (3 days for Shipway carriers).
- The job stops after 150 days (60 days for Shipway carriers).
- A tracking with **Manual Exception Removed** set is not asked about.

The admin can change these numbers in RIGPL Settings. Each update writes the status, the dates, the
receiver name and the scans. **Tracking Source** shows where the last update came from: Poll (the hourly
job) or Manual (the Get Status button).

### Proof of delivery

When a FedEx tracking becomes Delivered, the system gets the proof of delivery PDF in the background.
It attaches the PDF in **Proof of Delivery**. FedEx sometimes needs a few hours to make the PDF. A daily
job tries again for 30 days after delivery. You can also click **Shipment > Get Proof of Delivery**.

DTDC and Shipway carriers do not give a proof of delivery by API. Attach a scan of the signed copy by hand.

## Manual Exception Removed

Set **Manual Exception Removed** only when you know that the shipment is delivered, but the status does not
show Delivered. Also attach the proof of delivery. The hourly job then stops asking about this tracking,
and the tracking leaves the Pending Exceptions report.

## The tracking link for the customer

When a tracking is submitted, the customer email has a signed link to the tracking page. The page needs
the link: a guest cannot open a tracking page without it.

The link stops working:

- 7 days after delivery, or
- 90 days after the tracking was made, if it is not delivered.

The link stops at once when the status is RTO, Cancelled, Closed - No Update or Not Booked.

## Courier Tracking RIGPL report

Open **Courier Tracking RIGPL** and select a **Report Type**. Each type shows a chart and summary cards
above the table.

| Report Type | Shows |
|---|---|
| Pending Exceptions | Open trackings that are not delivered, of all dates. Use it each day. |
| Detailed | All trackings in the period. |
| Total AWB by Transporter | AWBs, delivered and exceptions for each transporter. |
| Avg Delivery Time | Average, longest and shortest days from pickup to delivery. |
| Old Exceptions | Submitted trackings in the period that are not delivered. |
| Carrier Performance | For each carrier and month: shipped, delivered, RTO, closed, P90 days and percent on time. |
| POD Coverage | Delivered trackings with and without a proof of delivery. |
| Cost vs Charged | Shipment cost against the courier amount on the invoice, and the trackings over the cost limit. |

All filters work on all types, except the dates on Pending Exceptions.
