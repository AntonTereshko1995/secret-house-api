from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from config import settings
from db.database import get_session
from repositories.booking_repository import BookingRepository
from schemas.booking import (
    AvailabilityRequest,
    AvailabilityResponse,
    BookedPeriodResponse,
    BookingCreateRequest,
    BookingCreateResponse,
)

router = APIRouter()

DbSession = Annotated[Session, Depends(get_session)]


@router.get("/periods", response_model=list[BookedPeriodResponse])
def get_booked_periods(
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
    bookings = repo.get_booked_periods(from_date=from_date, to_date=to_date)
    return [
        BookedPeriodResponse(
            checkIn=b.start_date,
            checkOut=b.end_date,
            bookingId=b.id,
        )
        for b in bookings
    ]


@router.post("/check-availability", response_model=AvailabilityResponse)
def check_availability(body: AvailabilityRequest, session: DbSession):
    """Check whether a proposed booking interval is free."""
    repo = BookingRepository(session)
    available = repo.is_available(body.startDatetime, body.endDatetime)
    return AvailabilityResponse(available=available)


@router.post(
    "",
    response_model=BookingCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(body: BookingCreateRequest, session: DbSession):
    """
    Submit a new booking from the web wizard.
    The booking is saved as unpaid (is_prepaymented=False).
    An admin notification can be wired up separately.
    """
    repo = BookingRepository(session)

    # Final availability check before saving
    if not repo.is_available(body.checkInDate, body.checkOutDate):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Выбранное время уже занято. Пожалуйста, выберите другую дату.",
        )

    try:
        booking = repo.create_booking(body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать бронирование. Попробуйте позже.",
        ) from exc

    # Notify bot only when no receipt is expected (gift cert fully covers the booking)
    no_receipt_expected = body.giftId and (body.prepaymentPrice or 0) == 0
    if settings.bot_notify_url and no_receipt_expected:
        try:
            import requests as _req
            _req.post(settings.bot_notify_url, json={"booking_id": booking.id}, timeout=5)
        except Exception:
            pass

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
    repo = BookingRepository(session)
    if not repo.get_by_id(booking_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено")

    if not settings.bot_receipt_url:
        return {"ok": True, "bookingId": booking_id}

    content = await file.read()
    filename = file.filename or "receipt"
    content_type = file.content_type or "application/octet-stream"

    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.bot_receipt_url,
            data={"booking_id": str(booking_id)},
            files={"file": (filename, content, content_type)},
        )

    if response.status_code == 200 and response.json().get("file_id"):
        repo.save_receipt_file_id(booking_id, response.json()["file_id"])

    return {"ok": True, "bookingId": booking_id}
