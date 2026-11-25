# Shipping Providers setup

This page is for the admin. It covers the Shipping Provider Account, the Transporters, the Shipping section of
RIGPL Settings and the tracking jobs. Dispatch staff: see [Carrier Tracking](../user/carrier-tracking.md).

The system talks to three providers:

| Provider | Used for | What the system does |
|---|---|---|
| FedEx | International express | Rates, booking, labels (with the booking), cancel, tracking, proof of delivery, address check, transit times |
| DTDC | Domestic | Booking, labels, cancel, tracking, pincode check |
| Shipway | Couriers with no API of their own (Speed Post, UPS, DHL and others) | Sends the AWB to Shipway, then tracks it there |

## 1. Clean up stale trackings (do this first)

A tracking is **stale** when it is submitted, its status is not final, and it is older than **Auto Close
Days** (RIGPL Settings, default 150). The hourly job stops asking about a tracking after 150 days, so a stale
tracking stays open for ever unless you close it.

Do the clean-up once after the first setup. Then do it again each time the stale count on the account
dashboard grows. The daily job does not close trackings. Only you do.

### Steps

Do these steps for each Shipping Provider Account (FedEx, DTDC, Shipway):

1. Open the Shipping Provider Account.
2. Read **Stale Open (all time)** on the dashboard. This is the number of stale trackings of the account.
3. Click **Actions > Re-apply Status Map**.
4. Wait for the message. It also goes to a Comment on the account.
5. Click **Actions > Close Stale Trackings**.
6. Wait for the message. Write down the counts.

Do Re-apply Status Map first. It works out the status of each open tracking again from the scans already
stored, with no call to the carrier. On dev it moved about 2,400 DTDC trackings from In Transit to Delivered.
Fewer trackings are then left for step 5, so step 5 makes fewer carrier calls.

### What each action does

**Re-apply Status Map**

- It reads the stored scans of each open or closed tracking of the account.
- It maps the scans with the Shipping Status Map (section 5). A Delivered scan wins, then an RTO scan, then
  the latest mapped scan.
- It does not change a tracking that is Delivered, RTO, Cancelled or Not Booked.
- It can change a Closed - No Update tracking only to Delivered or RTO.
- It adds a Comment to each changed tracking with the old and new status.

**Close Stale Trackings**

1. It asks the carrier about each stale tracking of the account one last time, and writes the result.
2. It sets each tracking that is still open to **Closed - No Update**, and unpublishes its tracking page.
3. It adds a Comment to each closed tracking with its old status.
4. It writes the counts (delivered, RTO, closed and others) to a Comment on the account.

Each action runs in the background, one at a time for each account. If you click again while it runs, you
get the message "already queued or running".

### For all accounts at once

From the bench folder:

```
bench --site <site> execute rigpl_erpnext.rigpl_erpnext.shipping.tracking.refresh_and_close_stale
```

To try it on a few trackings first, add `--kwargs "{'limit': 50}"`.

### Undo

There is no undo button. The Comment on each tracking holds the old status. To undo one tracking, set the
status back by hand.

## 2. Shipping Provider Account

Make one account for each set of credentials. Transporters link to the account.

Select the **Provider** first. The form then shows only the fields of that provider, in one section for
each provider. When you change the provider, the form clears the fields that the new provider does not use.
The save also deletes their stored secrets. For FedEx, Account Number, Client ID and Client Secret are
mandatory.

| Field | FedEx | DTDC | Shipway |
|---|---|---|---|
| Account Name | For example "FedEx" | For example "DTDC" | For example "Shipway" |
| Provider | FedEx | DTDC | Shipway |
| Enabled | Set | Set | Set |
| Sandbox | Set for the FedEx test server | Hidden | Hidden |
| FedEx API: Account Number | The 9-digit FedEx account number | Hidden | Hidden |
| FedEx API: Client ID, Client Secret | The REST API Key and the Secret Key | Hidden | Hidden |
| DTDC API: Customer Code, API Key | Hidden | The DTDC customer code and the Shipsy API key | Hidden |
| Login: Username, Password | Hidden | The DTDC tracking user and password | The Shipway username and license key |
| Base URL | Leave empty | Leave empty | Leave empty |
| Tracking Base URL, Serviceability URL | Hidden | Leave empty | Hidden |
| Webhook Secret, Webhook Enabled | Leave empty (section 7) | Leave empty | Hidden |

Leave a URL field empty to use the default URL of the provider. Fill it only when the provider gives you a new URL.

The secrets are kept encrypted. Do not write them in issues, comments or messages.

### FedEx

1. Sign in to the FedEx Developer Portal.
2. Make a project for production, with these APIs: Rate, Ship, Track, Track Document (proof of delivery),
   Address Validation, Service Availability, Trade Documents Upload.
3. Copy the API Key to **Client ID** and the Secret Key to **Client Secret**.
4. Enter the FedEx account number.
5. For tests, make a second account with the sandbox keys and set **Sandbox**.

A test booking puts `TEST-RIGPL` in the references. Cancel each test booking with **Delete Shipment**.

#### Electronic trade documents (ETD and EWO)

With ETD, FedEx sends our customs documents to customs electronically. Customs can then clear the shipment
before it arrives. ETD is active on the production account.

Each FedEx export needs an invoice PDF on the Carrier Tracking. The user attaches it in **Customs Invoice PDF**
before the booking. FedEx does not make an invoice of its own.

The Purpose of the Carrier Tracking sets the document type that FedEx gets:

| Purpose | Document type | The PDF to attach |
|---|---|---|
| SOLD | COMMERCIAL_INVOICE | The tax invoice of the Sales Invoice. |
| SAMPLE, GIFT, NOT_SOLD, REPAIR_AND_RETURN, PERSONAL_EFFECTS | PRO_FORMA_INVOICE | A pro forma invoice. FedEx does not take a pro forma invoice for SOLD. |

Catalogs and other printed matter go with a purpose other than SOLD, so they also need a pro forma invoice.

**Other Trade Document** is optional. It takes one more document, for example a packing list. FedEx gets
it as OTHER.

The booking checks the files before it calls FedEx:

- Customs Invoice PDF must be a PDF.
- Other Trade Document can be a PDF, an image (PNG, JPG), a text file, Word or Excel.
- Each file can be at most 5 MB.

Then the booking uploads the files to the FedEx Trade Documents Upload API, and books the shipment with the
ids that FedEx gives.

The destination can also need paper originals (EWO, "Electronic with Originals"). Then FedEx gives the number
of copies in the booking reply, and the label shows "EWO". The booking writes:

- **FedEx ETD**: the document types that FedEx took, for example COMMERCIAL_INVOICE.
- **Invoice Copies to Print**: the number of paper copies. It is empty when no paper copy is needed.

The daily job deletes the two files from each Delivered Carrier Tracking. FedEx and customs have them by then.
The Comment "Attachment Removed" on the tracking shows each deleted file.

Before the first booking, add the Trade Documents Upload API to the production project on the FedEx
Developer Portal.

Some countries do not accept ETD. Then FedEx refuses the booking, and the booking error shows the FedEx
message. Send the message to the FedEx account manager.

### DTDC

DTDC uses two services: Shipsy (`app.shipsy.in`) for booking, labels and cancel, and the DTDC tracking service
for tracking. Get the Shipsy API key and customer code, and the tracking user and password, from the DTDC
account manager.

### Shipway

Enter the Shipway username and license key. A tracking is sent to Shipway once, by the hourly job, in its first
20 days. Then the system tracks it by its Carrier Tracking name.

## 3. Transporters

Open each Transporter and fill the **Shipping API** section:

| Field | Meaning |
|---|---|
| Shipping Provider Account | The account of section 2. |
| API Mode | None: no API, enter the AWB by hand. Tracking Only: the system only tracks. Booking and Tracking: it also books, cancels and gets labels. |
| Provider Service Code | FedEx service type (for example INTERNATIONAL_PRIORITY), DTDC service type (for example PRIORITY), or the Shipway carrier id. |

Other fields that the shipping code reads:

- **Max Percent of Invoice Value**: the part of the shipment cost that you do not have to charge, as a percent
  of the invoice value. On a SOLD Sales Invoice, the courier charge must be at least the shipment cost less this
  part. A lower charge stops the save, unless **Bypass Courier Charged Check** is checked. A value of 0 means
  that you must charge the full cost. The check applies only when the system gets the cost: from a rate API
  (FedEx), or from the quote table (**Calculate Cost from Quote**, for example DTDC). Other transporters, for
  example the ones that Shipway tracks, are not checked. The system compares the values in the company
  currency, and converts a Sales Invoice at the rate of the invoice.
- **Invoice Courier Charges Account**: the account of the courier charge on the Sales Invoice. The system adds
  the item rows with this income account and the rows of the taxes table with this account.
- **Calculate Cost from Quote**: the cost comes from the Transporter quote table, not from the carrier.

## 4. RIGPL Settings, Shipping section

An empty field uses the default.

| Field | Default | Meaning |
|---|---|---|
| Poll Every (Hours) | 6 | A tracking is asked about again when its last update is older than this. |
| Poll Every With Webhooks (Hours) | 24 | The same, for an account with webhooks (not used yet, section 7). |
| Max Track Days (API) | 150 | DTDC and FedEx trackings older than this are not asked about. |
| Max Track Days (Shipway) | 60 | The same for Shipway carriers. |
| Shipway Push Max Days | 20 | A new AWB is sent to Shipway only in its first days. |
| Auto Close Days | 150 | Older open trackings are stale (section 1). |
| Unpublish Days After Delivery | 7 | The tracking page stops this many days after delivery. |
| Published Ctrack Days | 90 | The tracking page stops after this many days, also when not delivered. |

## 5. Shipping Status Map

Each carrier has its own status codes. The **Shipping Status Map** maps each code, or the start of a status
text, to one of the statuses of the system (Booked, In Transit, Delivered and the others).

When a carrier sends a code that is not in the map, the system adds a row with that code and an empty status.

1. Open the Shipping Status Map list.
2. Filter on an empty **Status**.
3. Set the status of each new row.
4. Run **Re-apply Status Map** on the account to fix the trackings that have the code.

## 6. Scheduled jobs

| Job | When | What it does |
|---|---|---|
| Poll open shipments | Hourly | Asks the carriers about the open trackings (the rules are in the user doc). Writes each batch with a fixed number of queries. |
| Push to Shipway | Hourly | Sends the new AWBs of Shipway carriers to Shipway. |
| Unpublish | Daily | Stops the tracking pages that have expired. |
| Proof of delivery retry | Daily | Gets the missing proof of delivery for FedEx trackings delivered in the last 30 days, at most 200 a day. |
| Proof of delivery | When a FedEx tracking becomes Delivered | Gets the PDF in the background. |

Carrier calls for each run:

- FedEx: 1 call for each 30 AWBs.
- DTDC: 1 call for each AWB. The DTDC tracking API takes one AWB at a time.
- Shipway: 1 call for each AWB, and 2 calls for each new AWB sent to Shipway.

## 7. Webhooks (not active)

A webhook lets the carrier send updates as they happen, so the hourly job can ask less often. The code does
not accept webhooks yet: see issue #171. FedEx needs a webhook project on the Developer Portal, and DTDC and
Shipway have not published their webhook formats.

Until then, leave **Webhook Enabled** off and **Webhook Secret** empty on each account.

## 8. Troubleshooting

Open the **Error Log** list and search for the title:

| Error Log title | Cause |
|---|---|
| Shipping: FedEx tracking failed (or DTDC, Shipway) | A batch of tracking calls failed. The other carriers continue. The batch is tried again at the next run. |
| Shipping: could not submit CTRACK… | A draft tracking got a status but could not be submitted. Open it and save it to see the error. |
| Shipping: Shipway push failed | Shipway refused an AWB. Check the Provider Service Code (the Shipway carrier id) on the Transporter. |
| Shipping: N proof of delivery fetches failed | FedEx had no POD yet for these trackings. The daily retry tries again. |
| Shipping: Booking failed, with an ETD or trade document message | The Trade Documents Upload API is not in the FedEx project, FedEx refused a file, or the destination does not accept ETD (section 2, FedEx). |

A form action shows its error at once, with the title "Shipping: … failed".

If no tracking updates for a whole account, check that the account is **Enabled**, that the secrets are
correct, and that the Transporters link to the account and have an API Mode.
