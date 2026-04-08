from datetime import date, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_session
from repositories.booking_repository import BookingRepository
from services.telegram_fallback import notify_new_booking, notify_receipt as tg_notify_receipt
from schemas.booking import (
    AvailabilityRequest,
    AvailabilityResponse,
    BookedPeriodResponse,
    BookingCreateRequest,
    BookingCreateResponse,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/periods", response_model=list[BookedPeriodResponse])
async def get_booked_periods(
    session: DbSession,
    from_date: date = Query(
        default_factory=lambda: date.today(),
        description="Start of date range (YYYY-MM-DD)",
    ),
    to_date: date = Query(
        default_factory=lambda: date.today() + timedelta(days=180),
        description="End of date range (YYYY-MM-DD)",
    ),
):
    """
    Return all active (prepaid) booked periods within the given date range.
    Used by the frontend calendar to mark unavailable dates.
    """
    repo = BookingRepository(session)
    bookings = await repo.get_booked_periods(from_date=from_date, to_date=to_date)
    return [
        BookedPeriodResponse(
            checkIn=b.start_date,
            checkOut=b.end_date,
            bookingId=b.id,
        )
        for b in bookings
    ]


@router.post("/check-availability", response_model=AvailabilityResponse)
async def check_availability(body: AvailabilityRequest, session: DbSession):
    """Check whether a proposed booking interval is free."""
    repo = BookingRepository(session)
    available = await repo.is_available(body.startDatetime, body.endDatetime)
    return AvailabilityResponse(available=available)


@router.post(
    "",
    response_model=BookingCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(body: BookingCreateRequest, session: DbSession):
    """
    Submit a new booking from the web wizard.
    The booking is saved as unpaid (is_prepaymented=False).
    An admin notification can be wired up separately.
    """
    repo = BookingRepository(session)

    # Final availability check before saving
    if not await repo.is_available(body.checkInDate, body.checkOutDate):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Выбранное время уже занято. Пожалуйста, выберите другую дату.",
        )

    try:
        booking = await repo.create_booking(body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать бронирование. Попробуйте позже.",
        ) from exc

    # Notify bot only when no receipt is expected (gift cert fully covers the booking)
    no_receipt_expected = body.giftId and (body.prepaymentPrice or 0) == 0
    if settings.bot_notify_url and no_receipt_expected:
        bot_ok = False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.post(
                    settings.bot_notify_url,
                    json={"booking_id": booking.id},
                )
                bot_ok = r.status_code == 200
        except Exception:
            pass
        if not bot_ok and settings.telegram_bot_token and settings.admin_chat_id:
            await notify_new_booking(settings.telegram_bot_token, settings.admin_chat_id, booking)

    return BookingCreateResponse(
        bookingId=booking.id,
        message=(
            "Бронирование создано! Пожалуйста, внесите предоплату "
            f"{int(booking.prepayment_price)} BYN для подтверждения."
        ),
    )


@router.post("/{booking_id}/receipt", status_code=status.HTTP_200_OK)
async def upload_receipt(
    booking_id: int,
    session: DbSession,
    file: UploadFile = File(...),
):
    """
    Accept a payment receipt photo/document from the user.
    Forwards it to the bot's HTTP endpoint which sends it to the admin Telegram chat.
    """
    import logging
    _log = logging.getLogger(__name__)

    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено")

    if not settings.bot_receipt_url:
        return {"ok": True, "bookingId": booking_id}

    content = await file.read()
    filename = file.filename or "receipt"
    content_type = file.content_type or "application/octet-stream"

    bot_ok = False
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                settings.bot_receipt_url,
                data={"booking_id": str(booking_id)},
                files={"file": (filename, content, content_type)},
            )
        if response.status_code == 200 and response.json().get("file_id"):
            await repo.save_receipt_file_id(booking_id, response.json()["file_id"])
            bot_ok = True
        else:
            _log.warning("bot receipt returned status=%s body=%s", response.status_code, response.text[:200])
    except Exception as e:
        _log.warning("bot receipt unavailable: %s", e)

    if not bot_ok and settings.telegram_bot_token and settings.admin_chat_id:
        _log.warning("bot unavailable — sending receipt via telegram fallback for booking %s", booking_id)
        try:
            ok = await tg_notify_receipt(
                settings.telegram_bot_token, settings.admin_chat_id,
                booking, filename, content, content_type,
            )
            _log.warning("telegram fallback result: %s", ok)
        except Exception as e:
            _log.warning("telegram fallback failed: %s", e)

    return {"ok": True, "bookingId": booking_id}
