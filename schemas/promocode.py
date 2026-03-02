from datetime import date
from typing import Optional

from pydantic import BaseModel


class PromoValidateRequest(BaseModel):
    code: str
    bookingDate: date   # ISO date string "YYYY-MM-DD"
    tariff: str         # frontend tariff ID, e.g. "incognito-daily"


class PromoValidateResponse(BaseModel):
    valid: bool
    discount: float     # discount amount in BYN (percentage × base price)
    discountPercentage: float
    message: str
    promocodeId: Optional[int] = None
