import random
import string
from datetime import datetime, timedelta
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_session
from db.models.gift import GiftBase
from db.models.tariff import Tariff
from services.telegram_fallback import notify_gift_purchase

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]

GIFT_CODE_LENGTH = 15
GIFT_VALIDITY_MONTHS = 6

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

# Maps frontend string IDs → Tariff enum
TARIFF_STR_TO_ENUM: dict[str, Tariff] = {
    "12h-standard": Tariff.HOURS_12,
    "daily-3plus": Tariff.DAY,
    "work-standard": Tariff.WORKER,
    "incognito-daily": Tariff.INCOGNITA_DAY,
    "incognito-12h": Tariff.INCOGNITA_HOURS,
    "incognito-work": Tariff.INCOGNITA_WORKER,
    "daily-couple": Tariff.DAY_FOR_COUPLE,
}


def _generate_code() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=GIFT_CODE_LENGTH))


class GiftValidateResponse(BaseModel):
    valid: bool
    message: str
    giftId: Optional[int] = None
    tariff: Optional[str] = None
    hasSauna: Optional[bool] = None
    hasSecretRoom: Optional[bool] = None
    hasAdditionalBedroom: Optional[bool] = None
    hasBathTub: Optional[bool] = None
    price: Optional[float] = None


class GiftPurchaseResponse(BaseModel):
    giftId: int
    code: str
    price: float
    message: str


@router.post("/purchase", response_model=GiftPurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase_gift(
    session: DbSession,
    tariff: str = Form(...),
    contact: str = Form(...),
    price: float = Form(...),
    hasSauna: bool = Form(False),
    hasSecretRoom: bool = Form(False),
    hasAdditionalBedroom: bool = Form(False),
    hasBathTub: bool = Form(False),
    file: Optional[UploadFile] = File(None),
):
    tariff_enum = TARIFF_STR_TO_ENUM.get(tariff)
    if tariff_enum is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown tariff: {tariff}")

    code = _generate_code()
    date_expired = datetime.now() + timedelta(days=GIFT_VALIDITY_MONTHS * 30)

    gift = GiftBase(
        buyer_contact=contact,
        tariff=tariff_enum,
        date_expired=date_expired,
        has_sauna=hasSauna,
        has_secret_room=hasSecretRoom,
        has_additional_bedroom=hasAdditionalBedroom,
        has_bath_tub=hasBathTub,
        price=price,
        code=code,
    )
    session.add(gift)
    await session.commit()
    await session.refresh(gift)

    # Read file bytes once (stream can only be read once)
    content: bytes | None = None
    filename: str | None = None
    content_type: str | None = None
    if file:
        content = await file.read()
        filename = file.filename
        content_type = file.content_type

    # Route notification through the bot's Flask server (same pattern as booking receipts)
    notified = False
    if settings.bot_gift_notify_url:
        try:
            form_data = {"gift_id": str(gift.id)}
            files_dict = {}
            if content and content_type:
                files_dict = {"file": (filename or "receipt", content, content_type)}
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    settings.bot_gift_notify_url,
                    data=form_data,
                    files=files_dict if files_dict else None,
                )
            notified = r.status_code == 200
        except Exception:
            pass

    # Fallback: direct Telegram API (if bot is unreachable and token is configured)
    if not notified and settings.telegram_bot_token and settings.admin_chat_id:
        await notify_gift_purchase(
            settings.telegram_bot_token,
            settings.admin_chat_id,
            gift,
            filename,
            content,
            content_type,
        )

    return GiftPurchaseResponse(
        giftId=gift.id,
        code=gift.code,
        price=gift.price,
        message="Заявка на сертификат принята",
    )


@router.get("/validate", response_model=GiftValidateResponse)
async def validate_gift_code(code: str = Query(...), session: DbSession = None):
    """
    Validate a gift certificate code.
    Returns tariff and included options so the frontend can pre-fill the booking wizard.
    """
    gift = await session.scalar(
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
        hasBathTub=gift.has_bath_tub,
        price=float(gift.price),
    )
