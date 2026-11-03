"""
The tracking statuses that every provider maps its own codes to (#168).
A tracking with a final status is not polled again.
"""
BOOKED = "Booked"
IN_TRANSIT = "In Transit"
OUT_FOR_DELIVERY = "Out for Delivery"
DELIVERED = "Delivered"
RTO = "RTO"
EXCEPTION = "Exception"
CANCELLED = "Cancelled"
NO_INFORMATION = "No Information"
CLOSED = "Closed - No Update"
NOT_BOOKED = "Not Booked"

# Older values that stay in the Select for the existing rows
LEGACY = ("Pickup Scheduled", "Posting Error", "Shipment Data Uploaded")

ALL_STATUSES = (
    BOOKED, IN_TRANSIT, OUT_FOR_DELIVERY, DELIVERED, RTO, EXCEPTION, CANCELLED, NO_INFORMATION, CLOSED,
    NOT_BOOKED,
) + LEGACY
FINAL_STATUSES = (DELIVERED, RTO, CANCELLED, CLOSED, NOT_BOOKED)
# Unpublished at once, without waiting for the days after delivery
UNPUBLISH_AT_ONCE = (RTO, CANCELLED, CLOSED, NOT_BOOKED)
