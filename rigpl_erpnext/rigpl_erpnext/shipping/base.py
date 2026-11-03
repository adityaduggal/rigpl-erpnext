"""
The provider interface (#168). An adapter in `providers/` gets plain data (no Frappe docs),
calls the carrier API and returns the dataclasses here. `tracking.py` writes the results.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

TEST_MARKING = "TEST-RIGPL"


class NotSupported(Exception):
    """The provider, or this adapter, cannot do this."""


class ProviderError(Exception):
    """The carrier API gave an error. The message never has a secret in it."""


@dataclass
class Address:
    name: str
    line1: str
    line2: str = ""
    city: str = ""
    state: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = ""
    country_code: str = ""
    phone: str = ""
    email: str = ""
    contact: str = ""
    company: str = ""
    tax_id: str = ""
    is_residential: bool = False


@dataclass
class Package:
    weight: float
    weight_uom: str = "kg"
    length: float = 0
    width: float = 0
    height: float = 0
    dimension_uom: str = "cm"
    declared_value: float = 0


@dataclass
class Commodity:
    description: str
    quantity: float
    quantity_uom: str
    unit_price: float
    weight: float
    hs_code: str = ""
    country_of_manufacture: str = "IN"


@dataclass
class ShipmentRequest:
    """Everything a provider needs to rate or book one Carrier Tracking."""
    reference: str  # the Carrier Tracking name
    service_code: str
    origin: Address
    destination: Address
    packages: List[Package]
    declared_value: float
    currency: str = "INR"
    invoice_number: str = ""
    purchase_order: str = ""
    purpose: str = "SOLD"
    is_inward: bool = False
    duties_payment_by: str = "RECIPIENT"
    description: str = "Cutting Tools"
    commodities: List[Commodity] = field(default_factory=list)
    ship_date: Optional[date] = None
    test_marking: bool = False

    @property
    def references(self) -> List[str]:
        """The references sent to the carrier. A test booking starts with TEST-RIGPL."""
        refs = [self.reference]
        return [TEST_MARKING] + refs if self.test_marking else refs


@dataclass
class Label:
    filename: str
    content: bytes


@dataclass
class BookingResult:
    awb: str
    package_ids: List[str]
    labels: List[Label] = field(default_factory=list)
    cost: Optional[float] = None
    currency: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Rate:
    service_code: str
    amount: float
    currency: str
    transit_days: Optional[int] = None
    delivery_date: Optional[date] = None
    oda: bool = False
    raw: dict = field(default_factory=dict)


@dataclass
class Scan:
    time: datetime
    location: str
    status_detail: str


@dataclass
class TrackingResult:
    awb: str
    status: str  # one of status.ALL_STATUSES
    status_code: str = ""
    found: bool = True
    pickup_date: Optional[datetime] = None
    expected_delivery_date: Optional[date] = None
    delivery_date_time: Optional[datetime] = None
    recipient: str = ""
    destination: str = ""
    scans: List[Scan] = field(default_factory=list)
    pod_available: bool = False


@dataclass
class Account:
    """A Shipping Provider Account with its secrets read once."""
    name: str
    provider: str
    is_sandbox: bool = False
    account_number: str = ""
    customer_code: str = ""
    client_id: str = ""
    username: str = ""
    client_secret: str = ""
    api_key: str = ""
    password: str = ""
    webhook_secret: str = ""
    base_url: str = ""
    tracking_base_url: str = ""
    serviceability_url: str = ""
    webhook_enabled: bool = False


class ShippingProvider:
    """Base adapter. Each method raises NotSupported unless the adapter has it.
    `resolve(code, text)` gives the Carrier Tracking status of a carrier code, or None.
    The registry passes one that reads Shipping Status Map. Without it, the adapter uses its
    own SEED_RULES (the rows that the seed patch adds), so tests need no database."""
    name = ""
    capabilities: FrozenSet[str] = frozenset()
    track_batch_size = 25
    check_service_before_booking = True
    SEED_RULES: Tuple[Tuple[str, str, str, str], ...] = ()

    def __init__(self, account: Account, resolve: Optional[Callable[[str, str], Optional[str]]] = None):
        self.account = account
        if resolve is None:
            from .status_map import StatusResolver, seed_rules

            resolve = StatusResolver(self.name, rules=seed_rules(self.name, self.SEED_RULES))
        self.resolve = resolve

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def get_rates(self, request: ShipmentRequest) -> List[Rate]:
        raise NotSupported(f"{self.name}: rates")

    def book(self, request: ShipmentRequest) -> BookingResult:
        raise NotSupported(f"{self.name}: booking")

    def cancel(self, awb: str) -> None:
        raise NotSupported(f"{self.name}: cancel")

    def get_labels(self, awb: str) -> List[Label]:
        raise NotSupported(f"{self.name}: labels")

    def track_many(self, shipments: Dict[str, str]) -> Dict[str, TrackingResult]:
        """`shipments` is {awb: reference (the Carrier Tracking name)}. Returns {awb: result}."""
        raise NotSupported(f"{self.name}: tracking")

    def get_pod(self, awb: str) -> Label:
        raise NotSupported(f"{self.name}: proof of delivery")

    def check_serviceability(self, origin: Address, destination: Address, cod: bool = False) -> Tuple[bool, str]:
        raise NotSupported(f"{self.name}: serviceability")

    def validate_address(self, address: Address) -> str:
        raise NotSupported(f"{self.name}: address check")

    def push(self, reference: str, awb: str, service_code: str) -> bool:
        raise NotSupported(f"{self.name}: push")
