from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from schemas.booking import TARIFF_ID_TO_INT


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str


class AdminBookingDetailResponse(BaseModel):
    """Admin view of a booking — includes user contact and source fields."""

    bookingId: int
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
    source: Optional[str]
    userContact: Optional[str]
    userName: Optional[str]


class AdminRescheduleRequest(BaseModel):
    checkInDate: datetime
    checkOutDate: datetime
    totalPrice: float


class AdminUpdatePriceRequest(BaseModel):
    totalPrice: float
    prepaymentPrice: float


class AdminUpdateTariffRequest(BaseModel):
    tariff: str
    totalPrice: float

    @field_validator("tariff")
    @classmethod
    def validate_tariff(cls, v: str) -> str:
        if v not in TARIFF_ID_TO_INT:
            raise ValueError(f"Unknown tariff: {v}")
        return v


class AdminUpdateServicesRequest(BaseModel):
    hasPhotoshoot: bool = False
    hasSauna: bool = False
    hasBathTub: bool = False
    hasExtraBedroom: bool = False
    hasSecretRoom: bool = False
    wineSelection: list[str] = []
    needsTransfer: bool = False
    transferAddress: Optional[str] = None
    totalPrice: float


class AdminBookingsPageResponse(BaseModel):
    items: list[AdminBookingDetailResponse]
    total: int
    page: int
    pageSize: int


class AdminUpdateResponse(BaseModel):
    bookingId: int
    message: str
