import logging
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select

from config import settings
from db.database import get_session
from db.models.booking import BookingBase
from db.models.tariff import Tariff
from dependencies import TelegramDep
from repositories.booking_repository import (
    BookingRepository,
    _to_booking_detail,
    _to_minsk_naive,
)
from schemas.booking import (
    TARIFF_ID_TO_INT,
    AvailabilityRequest,
    AvailabilityResponse,
    BookedPeriodResponse,
    BookingCreateRequest,
    BookingCreateResponse,
    BookingDetailResponse,
    BookingRescheduleRequest,
    BookingUpdateResponse,
    BookingUpdateServicesRequest,
    BookingUpdateTariffRequest,
)

_log = logging.getLogger(__name__)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def _get_booking_or_404(public_id: UUID, repo: BookingRepository) -> BookingBase:
    booking = await repo.get_by_public_id(public_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено")
    return booking


async def _get_booking_with_user_or_404(public_id: UUID, repo: BookingRepository) -> BookingBase:
    booking = await repo.get_by_public_id_with_user(public_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено")
    return booking


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
    repo = BookingRepository(session)
    available = await repo.is_available(body.startDatetime, body.endDatetime)
    return AvailabilityResponse(available=available)


@router.get("/my", response_model=list[BookingDetailResponse])
async def get_my_bookings(
    session: DbSession,
    contact: str = Query(
        ..., description="Telegram handle (@username) or phone number"
    ),
):
    repo = BookingRepository(session)
    bookings = await repo.get_bookings_by_contact(contact)
    return [_to_booking_detail(b) for b in bookings]


@router.get("/{public_id}", response_model=BookingDetailResponse)
async def get_booking_detail(public_id: UUID, session: DbSession):
    repo = BookingRepository(session)
    booking = await _get_booking_or_404(public_id, repo)
    return _to_booking_detail(booking)


@router.post(
    "",
    response_model=BookingCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_booking(
    body: BookingCreateRequest,
    session: DbSession,
    telegram: TelegramDep,
):
    repo = BookingRepository(session)

    if not await repo.is_available(body.checkInDate, body.checkOutDate):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Выбранное время уже занято. Пожалуйста, выберите другую дату.",
        )

    _log.info(
        "booking_create tariff=%s check_in=%s check_out=%s price=%s",
        body.tariff, body.checkInDate, body.checkOutDate, body.totalPrice,
    )
    try:
        booking = await repo.create_booking(body)
    except Exception as exc:
        _log.exception("booking_create failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать бронирование. Попробуйте позже.",
        ) from exc
    _log.info("booking_created id=%s public_id=%s", booking.id, booking.public_id)

    no_receipt_expected = bool(body.giftId and (body.prepaymentPrice or 0) == 0)
    try:
        await telegram.on_new_booking(
            booking.id, booking, no_receipt_expected=no_receipt_expected
        )
    except Exception as e:
        _log.warning("new_booking notify failed: %s", e, exc_info=True)

    return BookingCreateResponse(
        bookingId=booking.id,
        publicId=booking.public_id,
        message=(
            "Бронирование создано! Пожалуйста, внесите предоплату "
            f"{int(booking.prepayment_price)} BYN для подтверждения."
        ),
    )


@router.post("/{public_id}/receipt", status_code=status.HTTP_200_OK)
async def upload_receipt(
    public_id: UUID,
    session: DbSession,
    telegram: TelegramDep,
    file: UploadFile = File(...),
):
    repo = BookingRepository(session)
    booking = await _get_booking_with_user_or_404(public_id, repo)

    content = await file.read()
    filename = file.filename or "receipt"
    content_type = file.content_type or "application/octet-stream"

    file_id = None
    try:
        file_id = await telegram.on_receipt_uploaded(booking, filename, content, content_type)
    except Exception as e:
        _log.warning("receipt notify failed booking_id=%s: %s", booking.id, e, exc_info=True)

    if file_id:
        try:
            await repo.save_receipt_file_id(booking.id, file_id)
        except Exception as e:
            _log.warning("save_receipt_file_id failed: %s", e)

    return {"ok": True, "bookingId": booking.id}


@router.post("/{public_id}/cancel", response_model=BookingUpdateResponse)
async def cancel_booking(
    public_id: UUID,
    session: DbSession,
    telegram: TelegramDep,
):
    repo = BookingRepository(session)
    booking = await _get_booking_with_user_or_404(public_id, repo)
    try:
        await repo.cancel_booking(booking.id)
    except ValueError as exc:
        _log.warning("booking_cancel failed public_id=%s: %s", public_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("booking_cancelled id=%s public_id=%s", booking.id, public_id)
    try:
        await telegram.on_booking_cancelled(booking)
    except Exception as e:
        _log.warning("cancel notify failed: %s", e, exc_info=True)
    return BookingUpdateResponse(bookingId=booking.id, message="Бронирование отменено")


@router.patch("/{public_id}/tariff", response_model=BookingUpdateResponse)
async def update_booking_tariff(
    public_id: UUID,
    body: BookingUpdateTariffRequest,
    session: DbSession,
    telegram: TelegramDep,
):
    repo = BookingRepository(session)
    booking = await _get_booking_with_user_or_404(public_id, repo)
    old_tariff_name = telegram.tariff_display_name(booking.tariff)
    contact = booking.user.contact if booking.user else ""
    try:
        await repo.update_tariff(booking.id, body.tariff, body.totalPrice)
    except ValueError as exc:
        _log.warning("booking_update_tariff failed public_id=%s: %s", public_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info(
        "booking_tariff_updated id=%s tariff=%s price=%s", booking.id, body.tariff, body.totalPrice
    )
    new_tariff_int = TARIFF_ID_TO_INT.get(body.tariff)
    new_tariff_name = (
        telegram.tariff_display_name(Tariff(new_tariff_int))
        if new_tariff_int is not None
        else body.tariff
    )
    try:
        await telegram.on_tariff_changed(
            booking, old_tariff_name, new_tariff_name, contact, body.totalPrice
        )
    except Exception as e:
        _log.warning("tariff notify failed: %s", e, exc_info=True)
    return BookingUpdateResponse(bookingId=booking.id, message="Тариф успешно изменён")


@router.patch("/{public_id}/services", response_model=BookingUpdateResponse)
async def update_booking_services(
    public_id: UUID,
    body: BookingUpdateServicesRequest,
    session: DbSession,
    telegram: TelegramDep,
):
    repo = BookingRepository(session)
    booking = await _get_booking_with_user_or_404(public_id, repo)
    contact = booking.user.contact if booking.user else ""
    try:
        await repo.update_services(booking.id, body)
    except ValueError as exc:
        _log.warning("booking_update_services failed public_id=%s: %s", public_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("booking_services_updated id=%s", booking.id)
    try:
        await telegram.on_services_changed(
            booking,
            has_photoshoot=body.hasPhotoshoot,
            has_sauna=body.hasSauna,
            has_bath_tub=body.hasBathTub,
            has_extra_bedroom=body.hasExtraBedroom,
            has_secret_room=body.hasSecretRoom,
            wine_selection=body.wineSelection,
            needs_transfer=body.needsTransfer,
            transfer_address=body.transferAddress,
            new_price=body.totalPrice,
            contact=contact,
        )
    except Exception as e:
        _log.warning("services notify failed: %s", e, exc_info=True)
    return BookingUpdateResponse(bookingId=booking.id, message="Услуги успешно обновлены")


@router.patch("/{public_id}/reschedule", response_model=BookingUpdateResponse)
async def reschedule_booking(
    public_id: UUID,
    body: BookingRescheduleRequest,
    session: DbSession,
    telegram: TelegramDep,
):
    repo = BookingRepository(session)
    booking = await _get_booking_with_user_or_404(public_id, repo)
    contact = booking.user.contact if booking.user else ""
    old_start = booking.start_date
    old_end = booking.end_date
    try:
        updated = await repo.reschedule_booking(
            booking.id,
            body.checkInDate,
            body.checkOutDate,
            body.totalPrice,
        )
    except ValueError as exc:
        _log.warning("booking_reschedule failed public_id=%s: %s", public_id, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info(
        "booking_rescheduled id=%s check_in=%s check_out=%s",
        booking.id, body.checkInDate, body.checkOutDate,
    )
    try:
        await telegram.on_rescheduled(
            booking_id=booking.id,
            old_start=old_start,
            old_end=old_end,
            new_start=updated.start_date,
            new_end=updated.end_date,
            contact=contact,
        )
    except Exception as e:
        _log.warning("reschedule notify failed: %s", e, exc_info=True)
    return BookingUpdateResponse(bookingId=booking.id, message="Дата бронирования изменена")


@router.get("/{public_id}/availability-check", response_model=AvailabilityResponse)
async def check_reschedule_availability(
    public_id: UUID,
    session: DbSession,
    start: datetime = Query(..., description="New check-in datetime"),
    end: datetime = Query(..., description="New check-out datetime"),
):
    start_naive = _to_minsk_naive(start)
    end_naive = _to_minsk_naive(end)

    overlap = await session.scalar(
        select(BookingBase).where(
            and_(
                BookingBase.public_id != public_id,
                BookingBase.is_canceled == False,  # noqa: E712
                BookingBase.is_done == False,  # noqa: E712
                BookingBase.is_prepaymented == True,  # noqa: E712
                BookingBase.start_date < end_naive,
                BookingBase.end_date > start_naive,
            )
        )
    )
    return AvailabilityResponse(available=overlap is None)
