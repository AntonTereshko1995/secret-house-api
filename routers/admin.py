import base64
import hashlib
import hmac
import logging
import time
from datetime import date, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    status as http_status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

_log = logging.getLogger(__name__)
from db.database import get_session
from db.models.tariff import Tariff
from dependencies import TelegramDep
from repositories.booking_repository import (
    BookingRepository,
    _to_admin_booking_detail,
)
from schemas.admin import (
    AdminBookingDetailResponse,
    AdminBookingsPageResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminRescheduleRequest,
    AdminUpdatePriceRequest,
    AdminUpdateResponse,
    AdminUpdateServicesRequest,
    AdminUpdateTariffRequest,
)
from schemas.booking import BookedPeriodResponse, TARIFF_ID_TO_INT

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Token utilities
# ---------------------------------------------------------------------------


def _create_admin_token(username: str) -> str:
    expire = int(time.time()) + 86400 * 7  # 7 days
    payload = f"{username}:{expire}"
    sig = hmac.new(
        settings.admin_secret_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def _verify_admin_token(token: str) -> bool:
    try:
        data = base64.urlsafe_b64decode(token.encode()).decode()
        parts = data.split(":", 2)
        if len(parts) != 3:
            return False
        username, expire_str, sig = parts
        if int(expire_str) < int(time.time()):
            return False
        payload = f"{username}:{expire_str}"
        expected = hmac.new(
            settings.admin_secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


async def _verify_admin(
    x_admin_token: str = Header(..., alias="X-Admin-Token"),
) -> None:
    if not settings.admin_secret_key:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_SECRET_KEY не настроен",
        )
    if not _verify_admin_token(x_admin_token):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный токен администратора",
        )


AdminAuth = Annotated[None, Depends(_verify_admin)]


# ---------------------------------------------------------------------------
# Auth endpoint (public)
# ---------------------------------------------------------------------------


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest):
    """Authenticate with username and password; returns a 7-day HMAC token."""
    username_ok = hmac.compare_digest(body.username, settings.admin_username)
    password_ok = hmac.compare_digest(body.password, settings.admin_password)
    if not (username_ok and password_ok):
        _log.warning("admin_login failed username=%s", body.username)
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    _log.info("admin_login success username=%s", body.username)
    return AdminLoginResponse(token=_create_admin_token(body.username))


# ---------------------------------------------------------------------------
# Booking read endpoints
# ---------------------------------------------------------------------------


@router.get("/bookings", response_model=AdminBookingsPageResponse)
async def admin_get_bookings(
    _: AdminAuth,
    session: DbSession,
    sort_order: str = Query(default="desc", description="asc or desc"),
    status: str = Query(
        default="all", description="all|upcoming|past|canceled|done|unpaid"
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
):
    """Return paginated bookings with user contact, sorted and filtered."""
    repo = BookingRepository(session)
    bookings, total = await repo.admin_get_all_bookings(
        sort_order=sort_order, status=status, page=page, page_size=page_size
    )
    return AdminBookingsPageResponse(
        items=[_to_admin_booking_detail(b) for b in bookings],
        total=total,
        page=page,
        pageSize=page_size,
    )


@router.get("/bookings/periods", response_model=list[BookedPeriodResponse])
async def admin_get_booked_periods(
    _: AdminAuth,
    session: DbSession,
    from_date: date = Query(
        default_factory=lambda: date.today(),
        description="Start of date range (YYYY-MM-DD)",
    ),
    to_date: date = Query(
        default_factory=lambda: date.today() + timedelta(days=180),
        description="End of date range (YYYY-MM-DD)",
    ),
    exclude_id: int | None = Query(default=None, description="Booking ID to exclude"),
):
    """Return all active (non-canceled, non-done) booked periods for the admin calendar.
    Unlike the public endpoint, includes unprepaymented bookings so the admin sees
    every reserved slot. Excludes the booking with exclude_id when rescheduling.
    """
    repo = BookingRepository(session)
    bookings = await repo.admin_get_booked_periods(
        from_date=from_date, to_date=to_date, exclude_id=exclude_id
    )
    return [
        BookedPeriodResponse(
            checkIn=b.start_date,
            checkOut=b.end_date,
            bookingId=b.id,
        )
        for b in bookings
    ]


@router.get("/bookings/{booking_id}", response_model=AdminBookingDetailResponse)
async def admin_get_booking(
    booking_id: int,
    _: AdminAuth,
    session: DbSession,
):
    """Return full detail for a single booking including user contact."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    return _to_admin_booking_detail(booking)


# ---------------------------------------------------------------------------
# Booking write endpoints
# ---------------------------------------------------------------------------


@router.post("/bookings/{booking_id}/confirm", response_model=AdminUpdateResponse)
async def admin_confirm_booking(
    booking_id: int,
    _: AdminAuth,
    session: DbSession,
    telegram: TelegramDep,
):
    """Mark a booking as prepaymented (confirmed) — manual admin override."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    try:
        await repo.admin_confirm_booking(booking_id)
    except ValueError as exc:
        _log.warning("admin_confirm_booking failed id=%s: %s", booking_id, exc)
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("admin_confirm_booking id=%s", booking_id)
    try:
        await telegram.on_booking_confirmed(booking)
    except Exception as e:
        _log.warning("confirm notify failed: %s", e, exc_info=True)
    return AdminUpdateResponse(
        bookingId=booking_id, message="Бронирование подтверждено"
    )


@router.post("/bookings/{booking_id}/cancel", response_model=AdminUpdateResponse)
async def admin_cancel_booking(
    booking_id: int,
    _: AdminAuth,
    session: DbSession,
    telegram: TelegramDep,
):
    """Cancel any non-done, non-already-cancelled booking."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    try:
        await repo.admin_cancel_booking(booking_id)
    except ValueError as exc:
        _log.warning("admin_cancel_booking failed id=%s: %s", booking_id, exc)
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("admin_cancel_booking id=%s", booking_id)
    try:
        await telegram.on_booking_cancelled(booking)
    except Exception as e:
        _log.warning("cancel notify failed: %s", e, exc_info=True)
    return AdminUpdateResponse(bookingId=booking_id, message="Бронирование отменено")


@router.patch("/bookings/{booking_id}/tariff", response_model=AdminUpdateResponse)
async def admin_update_tariff(
    booking_id: int,
    body: AdminUpdateTariffRequest,
    _: AdminAuth,
    session: DbSession,
    telegram: TelegramDep,
):
    """Update tariff for any non-done, non-cancelled booking."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    old_tariff_name = telegram.tariff_display_name(booking.tariff)
    contact = booking.user.contact if booking.user else ""
    try:
        await repo.admin_update_tariff(booking_id, body.tariff, body.totalPrice)
    except ValueError as exc:
        _log.warning("admin_update_tariff failed id=%s: %s", booking_id, exc)
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("admin_update_tariff id=%s tariff=%s price=%s", booking_id, body.tariff, body.totalPrice)
    new_tariff_int = TARIFF_ID_TO_INT.get(body.tariff)
    new_tariff_name = (
        telegram.tariff_display_name(Tariff(new_tariff_int))
        if new_tariff_int is not None
        else body.tariff
    )
    try:
        await telegram.on_tariff_changed(booking, old_tariff_name, new_tariff_name, contact, body.totalPrice)
    except Exception as e:
        _log.warning("tariff notify failed: %s", e, exc_info=True)
    return AdminUpdateResponse(bookingId=booking_id, message="Тариф изменён")


@router.patch("/bookings/{booking_id}/services", response_model=AdminUpdateResponse)
async def admin_update_services(
    booking_id: int,
    body: AdminUpdateServicesRequest,
    _: AdminAuth,
    session: DbSession,
    telegram: TelegramDep,
):
    """Update additional services for any non-done, non-cancelled booking."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    contact = booking.user.contact if booking.user else ""
    try:
        await repo.admin_update_services(booking_id, body)
    except ValueError as exc:
        _log.warning("admin_update_services failed id=%s: %s", booking_id, exc)
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("admin_update_services id=%s", booking_id)
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
    return AdminUpdateResponse(bookingId=booking_id, message="Услуги обновлены")


@router.patch("/bookings/{booking_id}/reschedule", response_model=AdminUpdateResponse)
async def admin_reschedule_booking(
    booking_id: int,
    body: AdminRescheduleRequest,
    _: AdminAuth,
    session: DbSession,
    telegram: TelegramDep,
):
    """Reschedule booking unlimited times — admin bypass of is_date_changed."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    old_start = booking.start_date
    old_end = booking.end_date
    contact = booking.user.contact if booking.user else ""
    try:
        updated = await repo.admin_reschedule_booking(
            booking_id,
            body.checkInDate,
            body.checkOutDate,
            body.totalPrice,
        )
    except ValueError as exc:
        _log.warning("admin_reschedule failed id=%s: %s", booking_id, exc)
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("admin_reschedule id=%s check_in=%s check_out=%s", booking_id, body.checkInDate, body.checkOutDate)
    try:
        await telegram.on_rescheduled(
            old_start=old_start,
            old_end=old_end,
            new_start=updated.start_date,
            new_end=updated.end_date,
            contact=contact,
        )
    except Exception as e:
        _log.warning("reschedule notify failed: %s", e, exc_info=True)
    return AdminUpdateResponse(bookingId=booking_id, message="Дата перенесена")


@router.patch("/bookings/{booking_id}/price", response_model=AdminUpdateResponse)
async def admin_update_price(
    booking_id: int,
    body: AdminUpdatePriceRequest,
    _: AdminAuth,
    session: DbSession,
    telegram: TelegramDep,
):
    """Directly set total price and prepayment for any non-done, non-cancelled booking."""
    repo = BookingRepository(session)
    booking = await repo.get_by_id_with_user(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Бронирование не найдено"
        )
    old_price = booking.price
    old_prepayment = booking.prepayment_price
    contact = booking.user.contact if booking.user else ""
    try:
        await repo.admin_update_price(booking_id, body.totalPrice, body.prepaymentPrice)
    except ValueError as exc:
        _log.warning("admin_update_price failed id=%s: %s", booking_id, exc)
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    _log.info("admin_update_price id=%s total=%s prepayment=%s", booking_id, body.totalPrice, body.prepaymentPrice)
    try:
        await telegram.on_price_changed(
            booking,
            old_price=old_price,
            new_price=body.totalPrice,
            old_prepayment=old_prepayment,
            new_prepayment=body.prepaymentPrice,
            contact=contact,
        )
    except Exception as e:
        _log.warning("price notify failed: %s", e, exc_info=True)
    return AdminUpdateResponse(bookingId=booking_id, message="Стоимость обновлена")
