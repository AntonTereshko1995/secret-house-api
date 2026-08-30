from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

# Mapping from frontend tariff string IDs to Tariff enum integer values
TARIFF_ID_TO_INT: dict[str, int] = {
    "12h-standard": 0,
    "daily-3plus": 1,
    "work-standard": 2,
    "incognito-daily": 3,
    "incognito-12h": 4,
    "incognito-work": 5,
    "gift-certificate": 6,
    "daily-couple": 7,
}

# Reverse mapping: Tariff enum integer values → frontend string IDs
TARIFF_INT_TO_STR: dict[int, str] = {v: k for k, v in TARIFF_ID_TO_INT.items()}


class BookedPeriodResponse(BaseModel):
    """A booked time slot returned to the calendar."""

    checkIn: datetime
    checkOut: datetime
    bookingId: int


class AvailabilityRequest(BaseModel):
    startDatetime: datetime
    endDatetime: datetime


class AvailabilityResponse(BaseModel):
    available: bool


class BookingCreateRequest(BaseModel):
    """Payload sent by the frontend booking wizard."""

    # Dates & time
    checkInDate: datetime
    checkOutDate: datetime

    # Tariff
    tariff: str  # frontend string ID, e.g. "incognito-daily"
    giftCertificateCode: Optional[str] = None
    giftId: Optional[int] = None

    # Guests
    guestCount: int

    # Options
    hasPhotoshoot: bool = False
    hasSauna: bool = False
    bedroomType: Optional[str] = None  # "white" | "green" | None
    hasExtraBedroom: bool = False
    hasSecretRoom: bool = False
    hasBathTub: bool = False

    # Comment & promo
    comment: Optional[str] = None
    promocode: Optional[str] = None
    promocodeId: Optional[int] = None

    # Wine & transfer
    wineSelection: list[str] = []
    needsTransfer: bool = False
    transferAddress: Optional[str] = None

    # Price (calculated on frontend)
    totalPrice: float
    prepaymentPrice: Optional[float] = None

    # Contact
    contactType: str  # "telegram" | "phone"
    telegram: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("tariff")
    @classmethod
    def validate_tariff(cls, v: str) -> str:
        if v not in TARIFF_ID_TO_INT:
            raise ValueError(f"Unknown tariff: {v}")
        return v

    @property
    def contact(self) -> str:
        """Returns the primary contact identifier."""
        if self.contactType == "telegram" and self.telegram:
            return self.telegram  # already formatted as @username by frontend
        return self.phone or ""

    @property
    def tariff_int(self) -> int:
        return TARIFF_ID_TO_INT[self.tariff]

    @property
    def wine_preference_str(self) -> Optional[str]:
        return ", ".join(self.wineSelection) if self.wineSelection else None

    @property
    def has_white_bedroom(self) -> bool:
        return self.hasExtraBedroom or self.bedroomType == "white"

    @property
    def has_green_bedroom(self) -> bool:
        return self.hasExtraBedroom or self.bedroomType == "green"


class BookingCreateResponse(BaseModel):
    bookingId: int
    publicId: UUID
    message: str


class BookingDetailResponse(BaseModel):
    """Full booking detail returned to the frontend."""

    bookingId: int
    publicId: UUID
    startDate: datetime
    endDate: datetime
    tariff: str
    guestCount: int
    hasPhotoshoot: bool
    hasSauna: bool
    hasExtraBedroom: bool
    hasSecretRoom: bool
    hasBathTub: bool
    isCanceled: bool
    isDateChanged: bool
    isPrepaymented: bool
    isDone: bool
    totalPrice: float
    prepaymentPrice: float
    comment: Optional[str]
    wineSelection: list[str]
    transferAddress: Optional[str]
    isFuture: bool
    canModify: bool
    canReschedule: bool
    canCancel: bool
    canPay: bool


class BookingUpdateTariffRequest(BaseModel):
    tariff: str
    totalPrice: float

    @field_validator("tariff")
    @classmethod
    def validate_tariff(cls, v: str) -> str:
        if v not in TARIFF_ID_TO_INT:
            raise ValueError(f"Unknown tariff: {v}")
        return v


class BookingUpdateServicesRequest(BaseModel):
    hasPhotoshoot: bool = False
    hasSauna: bool = False
    hasBathTub: bool = False
    hasExtraBedroom: bool = False
    hasSecretRoom: bool = False
    wineSelection: list[str] = []
    needsTransfer: bool = False
    transferAddress: Optional[str] = None
    totalPrice: float


class BookingRescheduleRequest(BaseModel):
    checkInDate: datetime
    checkOutDate: datetime
    totalPrice: float


class BookingUpdateResponse(BaseModel):
    bookingId: int
    message: str
