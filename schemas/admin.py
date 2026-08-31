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
    bedroomType: Optional[str] = None


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
    bedroomType: Optional[str] = None


class AdminBookingsPageResponse(BaseModel):
    items: list[AdminBookingDetailResponse]
    total: int
    page: int
    pageSize: int


class AdminUpdateResponse(BaseModel):
    bookingId: int
    message: str


# ---------------------------------------------------------------------------
# Statistics response models
# ---------------------------------------------------------------------------


class AdminStatsSummary(BaseModel):
    totalBookings: int
    activeBookings: int
    canceledBookings: int
    doneBookings: int
    totalRevenue: float
    avgPrice: float
    prepaidCount: int
    cancelRate: float


class AdminStatsMonthly(BaseModel):
    year: int
    month: int
    total: int
    done: int
    canceled: int
    revenue: float


class AdminStatsTariff(BaseModel):
    tariff: str
    total: int
    revenue: float
    avgPrice: float
    cancelCount: int


class AdminStatsSource(BaseModel):
    source: str
    total: int
    done: int
    canceled: int
    cancelRate: float


class AdminStatsDow(BaseModel):
    dow: int
    dayName: str
    total: int


class AdminStatsDuration(BaseModel):
    bucket: str
    label: str
    total: int


class AdminStatsGuests(BaseModel):
    guestCount: int
    total: int


class AdminStatsOptions(BaseModel):
    hasSauna: int
    hasWhiteBedroom: int
    hasGreenBedroom: int
    hasSecretRoom: int
    hasPhotoshoot: int
    hasBathTub: int
    saunaAvgPrice: float
    noSaunaAvgPrice: float


class AdminStatsUsers(BaseModel):
    total: int
    active: int
    withBookings: int
    withCompleted: int
    repeatCustomers: int
    loyalCustomers: int
    telegramAccounts: int


class AdminStatsGifts(BaseModel):
    total: int
    paid: int
    used: int
    expired: int
    avgPrice: float


class AdminStatisticsResponse(BaseModel):
    summary: AdminStatsSummary
    monthlyBreakdown: list[AdminStatsMonthly]
    tariffBreakdown: list[AdminStatsTariff]
    sourceBreakdown: list[AdminStatsSource]
    dayOfWeekBreakdown: list[AdminStatsDow]
    durationBreakdown: list[AdminStatsDuration]
    guestCountBreakdown: list[AdminStatsGuests]
    options: AdminStatsOptions
    users: AdminStatsUsers
    gifts: AdminStatsGifts
    generatedAt: datetime
