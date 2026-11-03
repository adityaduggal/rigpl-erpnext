"""
The carrier codes that each provider starts with in Shipping Status Map (#168). The seed patch
`shipping_status_map_seed` adds the rows that are missing and never changes a row that exists,
so edit a status in the Shipping Status Map list, not here. A new provider adds one entry.

Each row is (match_on, carrier code or text, status, carrier description).
"""
from . import status as st

# The scan codes (strCode) seen on dev from 2025 to 2026, and the header text. The seed patch
# adds them to Shipping Status Map. Edit the statuses there, not here.
_DTDC_IN_TRANSIT = ("PCUP", "CDIN", "CDOUT", "OBMN", "IBMN", "INSCAN", "IPMF", "OPMF", "IBMD", "OBMD", "ARAP",
               "RADCDIN", "FDMS")
DTDC = (
    ("Code", "DLV", st.DELIVERED, "Delivered"),
    ("Code", "OUTDLV", st.OUT_FOR_DELIVERY, "Out For Delivery"),
    ("Code", "PREPERD", st.OUT_FOR_DELIVERY, "Scheduled for Delivery"),
    ("Code", "NONDLV", st.EXCEPTION, "Undelivered"),
    ("Code", "SVD", st.EXCEPTION, "Wrong Pincode"),
    ("Code", "ORMF", st.EXCEPTION, "Mis Route"),
    ("Code", "IRMF", st.EXCEPTION, "Shipment Misroute"),
    ("Code", "PCNO", st.EXCEPTION, "Not Picked"),
    ("Code", "RTRB", st.EXCEPTION, "Return to Processing Center"),
    ("Code", "SETRTO", st.RTO, "Set RTO initiated"),
    ("Code Starts With", "RTO", st.RTO, "RTO"),
    ("Code", "BKD", st.BOOKED, "Shipment Booked"),
    ("Code", "SPL", st.BOOKED, "Softdata Upload"),
    ("Code", "PCAW", st.BOOKED, "Pickup Awaited"),
    ("Code", "PCSC", st.BOOKED, "Pickup Scheduled"),
    ("Code", "PCRA", st.BOOKED, "Pickup Rescheduled"),
    ("Text Contains", "DELIVERED", st.DELIVERED, "Header status"),
    ("Text Contains", "UNDELIVERED", st.EXCEPTION, "Header status"),
    ("Text Contains", "NOT DELIVERED", st.EXCEPTION, "Header status"),
    ("Text Contains", "OUT FOR DELIVERY", st.OUT_FOR_DELIVERY, "Header status"),
    ("Text Contains", "CANCEL", st.CANCELLED, "Header status"),
) + tuple(("Code", code, st.IN_TRANSIT, "In Transit") for code in _DTDC_IN_TRANSIT)


# The codes in the Shipway Settings docstring. The seed patch adds them to Shipping Status Map.
SHIPWAY = (
    ("Code", "DEL", st.DELIVERED, "Delivered"),
    ("Code", "OOD", st.OUT_FOR_DELIVERY, "Out for Delivery"),
    ("Code", "DNB", st.OUT_FOR_DELIVERY, "Delivery Next Day"),
    ("Code", "INT", st.IN_TRANSIT, "In Transit"),
    ("Code", "PKP", st.IN_TRANSIT, "Picked Up"),
    ("Code", "RTO", st.RTO, "RTO"),
    ("Code", "RTD", st.RTO, "RTO Delivered"),
    ("Code", "CAN", st.CANCELLED, "Cancelled"),
    ("Code", "UND", st.EXCEPTION, "Undelivered"),
    ("Code", "ONH", st.EXCEPTION, "On Hold"),
    ("Code", "NWI", st.EXCEPTION, "Network Issue"),
    ("Code", "ODA", st.EXCEPTION, "Out of Delivery Area"),
    ("Code", "NFI", st.NO_INFORMATION, "Not Found/Incorrect"),
    ("Code", "SCH", st.BOOKED, "Shipment Booked"),
    ("Code", "OTH", st.IN_TRANSIT, "Others"),
    ("Code", "SMD", st.EXCEPTION, "Delivery Delayed"),
    ("Code", "22", st.EXCEPTION, "Address Incorrect"),
    ("Code", "23", st.EXCEPTION, "Delivery Attempted"),
    ("Code", "24", st.EXCEPTION, "Pending- Undelivered"),
    ("Code", "25", st.EXCEPTION, "Closed"),
    ("Code", "CRTA", st.EXCEPTION, "Customer Refused"),
    ("Code", "CNA", st.EXCEPTION, "Consignee Unavailable"),
    ("Code", "DEX", st.EXCEPTION, "Delivery Exception"),
    ("Code", "DRE", st.EXCEPTION, "Delivery Rescheduled"),
    ("Code", "PNR", st.EXCEPTION, "COD Payment Not Ready"),
    ("Code", "LOST", st.EXCEPTION, "Lost"),
)


# FedEx Track API: latestStatusDetail.code (FedEx "Track Status Codes")
_FEDEX = (
    ("DL", st.DELIVERED, "Delivered"),
    ("OD", st.OUT_FOR_DELIVERY, "On FedEx vehicle for delivery"),
    ("ED", st.OUT_FOR_DELIVERY, "Enroute to Delivery"),
    ("OC", st.BOOKED, "Shipment information sent to FedEx (label created)"),
    ("PU", st.IN_TRANSIT, "Picked up"),
    ("PX", st.IN_TRANSIT, "Picked up (see Details)"),
    ("IT", st.IN_TRANSIT, "In transit"),
    ("IX", st.IN_TRANSIT, "In transit (see Details)"),
    ("AR", st.IN_TRANSIT, "Arrived at FedEx location"),
    ("AF", st.IN_TRANSIT, "At local FedEx facility"),
    ("AP", st.IN_TRANSIT, "At Pickup"),
    ("AA", st.IN_TRANSIT, "At Airport"),
    ("AC", st.IN_TRANSIT, "At Canada Post facility"),
    ("DP", st.IN_TRANSIT, "Left FedEx origin facility"),
    ("LO", st.IN_TRANSIT, "Left Origin"),
    ("OF", st.IN_TRANSIT, "At FedEx origin facility"),
    ("FD", st.IN_TRANSIT, "At FedEx destination facility"),
    ("SF", st.IN_TRANSIT, "At Sort Facility"),
    ("PF", st.IN_TRANSIT, "Plane in Flight"),
    ("PL", st.IN_TRANSIT, "Plane Landed"),
    ("TR", st.IN_TRANSIT, "Transfer"),
    ("CC", st.IN_TRANSIT, "International shipment release (cleared customs)"),
    ("CP", st.IN_TRANSIT, "Clearance in Progress"),
    ("EA", st.IN_TRANSIT, "Export Approved"),
    ("PM", st.IN_TRANSIT, "In Progress"),
    ("CH", st.IN_TRANSIT, "Location Changed"),
    ("DS", st.IN_TRANSIT, "Vehicle Dispatched"),
    ("EP", st.IN_TRANSIT, "Enroute to Pickup"),
    ("EO", st.IN_TRANSIT, "Enroute to Origin Airport"),
    ("SP", st.IN_TRANSIT, "Split Status"),
    ("DE", st.EXCEPTION, "Delivery Exception"),
    ("SE", st.EXCEPTION, "Shipment Exception"),
    ("DD", st.EXCEPTION, "Delivery Delay"),
    ("DY", st.EXCEPTION, "Delay"),
    ("PD", st.EXCEPTION, "Pickup Delay"),
    ("CD", st.EXCEPTION, "Clearance Delay"),
    ("HL", st.EXCEPTION, "Hold at Location"),
    ("RS", st.RTO, "Return to Shipper"),
    ("CA", st.CANCELLED, "Shipment Cancelled"),
)
FEDEX = tuple(("Code", code, status, text) for code, status, text in _FEDEX) + (
    ("Text Contains", "DELIVERED", st.DELIVERED, "Status description"),
    ("Text Contains", "OUT FOR DELIVERY", st.OUT_FOR_DELIVERY, "Status description"),
    ("Text Contains", "RETURN TO SHIPPER", st.RTO, "Status description"),
    ("Text Contains", "EXCEPTION", st.EXCEPTION, "Status description"),
)


SEED_RULES = {"DTDC": DTDC, "Shipway": SHIPWAY, "FedEx": FEDEX}
