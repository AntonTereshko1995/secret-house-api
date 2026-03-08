from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.database import get_session
from db.models.gift import GiftBase

router = APIRouter()

DbSession = Annotated[Session, Depends(get_session)]

# Maps Tariff enum int values → frontend string IDs
TARIFF_INT_TO_STR: dict[int, str] = {
    0: "12h-standard",
    1: "daily-3plus",
    2: "work-standard",
    3: "incognito-daily",
    4: "incognito-12h",
    5: "incognito-work",
    6: "gift-certificate",
    7: "daily-couple",
}


class GiftValidateResponse(BaseModel):
    valid: bool
    message: str
    giftId: Optional[int] = None
    tariff: Optional[str] = None
    hasSauna: Optional[bool] = None
    hasSecretRoom: Optional[bool] = None
    hasAdditionalBedroom: Optional[bool] = None
    price: Optional[float] = None


@router.get("/validate", response_model=GiftValidateResponse)
def validate_gift_code(code: str = Query(...), session: DbSession = None):
    """
    Validate a gift certificate code.
    Returns tariff and included options so the frontend can pre-fill the booking wizard.
    """
    gift = session.scalar(
        select(GiftBase).where(
            (GiftBase.code == code.strip().upper())
            & (GiftBase.is_paymented == True)  # noqa: E712
            & (GiftBase.is_done == False)  # noqa: E712
            & (GiftBase.date_expired > datetime.now())
        )
    )

    if not gift:
        return GiftValidateResponse(
            valid=False,
            message="Сертификат не найден, уже использован или истёк срок действия",
        )

    tariff_int = gift.tariff.value if hasattr(gift.tariff, "value") else int(gift.tariff)
    tariff_str = TARIFF_INT_TO_STR.get(tariff_int, "12h-standard")

    return GiftValidateResponse(
        valid=True,
        message="Сертификат действителен",
        giftId=gift.id,
        tariff=tariff_str,
        hasSauna=gift.has_sauna,
        hasSecretRoom=gift.has_secret_room,
        hasAdditionalBedroom=gift.has_additional_bedroom,
        price=float(gift.price),
    )
