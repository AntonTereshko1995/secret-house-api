from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class PromoValidateRequest(BaseModel):
    code: str
    bookingDate: date  # ISO date string "YYYY-MM-DD"
    tariff: str  # frontend tariff ID, e.g. "incognito-daily"


class PromoValidateResponse(BaseModel):
    valid: bool
    discount: float  # discount amount in BYN (percentage × base price)
    discountPercentage: float
    message: str
    promocodeId: Optional[int] = None


class PromoAdminRead(BaseModel):
    """Full promo DTO returned to the admin frontend."""

    id: int
    name: str
    promocodeType: int  # 1=BOOKING_DATES, 2=USAGE_PERIOD
    dateFrom: date
    dateTo: date
    discountPercentage: float
    applicableTariffs: Optional[list[int]]  # None = all tariffs
    isActive: bool
    createdAt: datetime


class PromoCreateRequest(BaseModel):
    """Payload for both POST (create) and PATCH (full-replace update)."""

    name: str
    promocodeType: int = 1
    dateFrom: date
    dateTo: date
    discountPercentage: float
    applicableTariffs: Optional[list[int]] = None
    isActive: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Имя промокода не может быть пустым")
        return cleaned

    @field_validator("promocodeType")
    @classmethod
    def validate_type(cls, v: int) -> int:
        if v not in (1, 2):
            raise ValueError("promocodeType должен быть 1 (по дате заезда) или 2 (по периоду)")
        return v

    @field_validator("discountPercentage")
    @classmethod
    def validate_discount(cls, v: float) -> float:
        if not (0 < v <= 100):
            raise ValueError("discountPercentage должен быть в диапазоне (0, 100]")
        return v

    @model_validator(mode="after")
    def check_dates(self) -> "PromoCreateRequest":
        if self.dateTo < self.dateFrom:
            raise ValueError("dateTo должна быть >= dateFrom")
        return self
