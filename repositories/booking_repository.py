from datetime import date, datetime
from typing import Sequence
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models.booking import BookingBase
from db.models.gift import GiftBase
from db.models.tariff import Tariff
from db.models.user import UserBase
from repositories.base import BaseRepository
from repositories.user_repository import UserRepository
from schemas.admin import (
    AdminBookingDetailResponse,
    AdminStatsDow,
    AdminStatsDuration,
    AdminStatsGifts,
    AdminStatsGuests,
    AdminStatsMonthly,
    AdminStatsOptions,
    AdminStatsSource,
    AdminStatsSummary,
    AdminStatsTariff,
    AdminStatsUsers,
    AdminStatisticsResponse,
    AdminUpdateServicesRequest,
)
from schemas.booking import (
    BookingCreateRequest,
    BookingDetailResponse,
    BookingUpdateServicesRequest,
    TARIFF_ID_TO_INT,
    TARIFF_INT_TO_STR,
)


_MINSK_TZ = ZoneInfo("Europe/Minsk")


def _to_minsk_naive(dt: datetime) -> datetime:
    """Convert a UTC-aware (or any tz-aware) datetime to a naive Minsk-local datetime."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(_MINSK_TZ)
    return dt.replace(tzinfo=None)


def _to_booking_detail(b: BookingBase) -> BookingDetailResponse:
    """Map ORM model to API response DTO."""
    now_naive = datetime.now()
    tariff_str = TARIFF_INT_TO_STR.get(b.tariff.value, "12h-standard")

    wine_list = (
        [w.strip() for w in b.wine_preference.split(",") if w.strip()]
        if b.wine_preference
        else []
    )

    has_extra = b.has_white_bedroom and b.has_green_bedroom
    bedroom_type: str | None = None
    if b.has_white_bedroom and not b.has_green_bedroom:
        bedroom_type = "white"
    elif b.has_green_bedroom and not b.has_white_bedroom:
        bedroom_type = "green"

    is_future = b.start_date > now_naive
    not_closed = not b.is_canceled and not b.is_done
    can_modify = is_future and b.is_prepaymented and not_closed
    can_reschedule = can_modify and not b.is_date_changed
    can_cancel = is_future and not_closed
    can_pay = not b.is_prepaymented and not_closed

    return BookingDetailResponse(
        bookingId=b.id,
        publicId=b.public_id,
        startDate=b.start_date,
        endDate=b.end_date,
        tariff=tariff_str,
        guestCount=b.number_of_guests,
        hasPhotoshoot=b.has_photoshoot,
        hasSauna=b.has_sauna,
        hasExtraBedroom=has_extra,
        hasSecretRoom=b.has_secret_room,
        hasBathTub=b.has_bath_tub,
        isCanceled=b.is_canceled,
        isDateChanged=b.is_date_changed,
        isPrepaymented=b.is_prepaymented,
        isDone=b.is_done,
        totalPrice=b.price,
        prepaymentPrice=b.prepayment_price,
        comment=b.comment,
        wineSelection=wine_list,
        transferAddress=b.transfer_address,
        isFuture=is_future,
        canModify=can_modify,
        canReschedule=can_reschedule,
        canCancel=can_cancel,
        canPay=can_pay,
        bedroomType=bedroom_type,
    )


def _assert_can_modify(booking: BookingBase) -> None:
    """Raise ValueError if booking is not eligible for modification."""
    now_naive = datetime.now()
    is_future = booking.start_date > now_naive
    can_modify = (
        is_future
        and booking.is_prepaymented
        and not booking.is_canceled
        and not booking.is_done
    )
    if not can_modify:
        raise ValueError("Это бронирование нельзя изменить")


def _assert_admin_can_modify(booking: BookingBase) -> None:
    """Admin guard — weaker than user guard: only blocks canceled/done bookings."""
    if booking.is_canceled:
        raise ValueError("Бронирование уже отменено")
    if booking.is_done:
        raise ValueError("Бронирование уже завершено")


def _to_admin_booking_detail(b: BookingBase) -> AdminBookingDetailResponse:
    """Map ORM model (with user eagerly loaded) to admin API response."""
    now_naive = datetime.now()
    tariff_str = TARIFF_INT_TO_STR.get(b.tariff.value, "12h-standard")
    wine_list = (
        [w.strip() for w in b.wine_preference.split(",") if w.strip()]
        if b.wine_preference
        else []
    )
    has_extra = b.has_white_bedroom and b.has_green_bedroom
    admin_bedroom_type: str | None = None
    if b.has_white_bedroom and not b.has_green_bedroom:
        admin_bedroom_type = "white"
    elif b.has_green_bedroom and not b.has_white_bedroom:
        admin_bedroom_type = "green"

    return AdminBookingDetailResponse(
        bookingId=b.id,
        startDate=b.start_date,
        endDate=b.end_date,
        tariff=tariff_str,
        guestCount=b.number_of_guests,
        hasPhotoshoot=b.has_photoshoot,
        hasSauna=b.has_sauna,
        hasExtraBedroom=has_extra,
        hasSecretRoom=b.has_secret_room,
        hasBathTub=b.has_bath_tub,
        isCanceled=b.is_canceled,
        isDateChanged=b.is_date_changed,
        isPrepaymented=b.is_prepaymented,
        isDone=b.is_done,
        totalPrice=b.price,
        prepaymentPrice=b.prepayment_price,
        comment=b.comment,
        wineSelection=wine_list,
        transferAddress=b.transfer_address,
        isFuture=b.start_date > now_naive,
        source=b.source,
        userContact=b.user.contact if b.user else None,
        userName=b.user.user_name if b.user else None,
        bedroomType=admin_bedroom_type,
    )


class BookingRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.user_repo = UserRepository(session)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, booking_id: int) -> BookingBase | None:
        """Return a single booking by primary key."""
        return await self.session.scalar(
            select(BookingBase).where(BookingBase.id == booking_id)
        )

    async def get_by_id_with_user(self, booking_id: int) -> BookingBase | None:
        """Return a booking with its user eagerly loaded."""
        return await self.session.scalar(
            select(BookingBase)
            .options(selectinload(BookingBase.user))
            .where(BookingBase.id == booking_id)
        )

    async def get_by_public_id(self, public_id: UUID) -> BookingBase | None:
        """Return a single booking by its public UUID."""
        return await self.session.scalar(
            select(BookingBase).where(BookingBase.public_id == public_id)
        )

    async def get_by_public_id_with_user(self, public_id: UUID) -> BookingBase | None:
        """Return a booking with its user eagerly loaded, looked up by public UUID."""
        return await self.session.scalar(
            select(BookingBase)
            .options(selectinload(BookingBase.user))
            .where(BookingBase.public_id == public_id)
        )

    async def get_bookings_by_contact(self, contact: str) -> Sequence[BookingBase]:
        """Return all bookings for the user identified by their contact string."""
        result = await self.session.scalars(
            select(BookingBase)
            .join(UserBase, BookingBase.user_id == UserBase.id)
            .where(UserBase.contact == contact.strip())
            .order_by(BookingBase.start_date.desc())
        )
        return result.all()

    async def save_receipt_file_id(self, booking_id: int, file_id: str) -> None:
        """Persist the Telegram file_id of the payment receipt."""
        booking = await self.session.get(BookingBase, booking_id)
        if booking:
            booking.receipt_file_id = file_id
            await self.session.commit()

    async def get_booked_periods(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> Sequence[BookingBase]:
        """Return active (prepaid, not canceled, not done) bookings in a date range."""
        query = select(BookingBase).where(
            and_(
                BookingBase.is_prepaymented == True,  # noqa: E712
                BookingBase.is_canceled == False,  # noqa: E712
                BookingBase.is_done == False,  # noqa: E712
            )
        )

        if from_date is not None:
            from_dt = datetime.combine(from_date, datetime.min.time())
            query = query.where(BookingBase.end_date >= from_dt)

        if to_date is not None:
            to_dt = datetime.combine(to_date, datetime.max.time())
            query = query.where(BookingBase.start_date <= to_dt)

        query = query.order_by(BookingBase.start_date)
        result = await self.session.scalars(query)
        return result.all()

    async def admin_get_booked_periods(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        exclude_id: int | None = None,
    ) -> Sequence[BookingBase]:
        """Return all active (non-canceled, non-done) bookings for admin calendar.
        Unlike get_booked_periods, includes unprepaymented bookings so the admin
        sees every reserved slot. Optionally excludes one booking by ID.
        """
        conditions = [
            BookingBase.is_canceled == False,  # noqa: E712
            BookingBase.is_done == False,  # noqa: E712
        ]
        if exclude_id is not None:
            conditions.append(BookingBase.id != exclude_id)
        if from_date is not None:
            from_dt = datetime.combine(from_date, datetime.min.time())
            conditions.append(BookingBase.end_date >= from_dt)
        if to_date is not None:
            to_dt = datetime.combine(to_date, datetime.max.time())
            conditions.append(BookingBase.start_date <= to_dt)

        query = select(BookingBase).where(and_(*conditions)).order_by(BookingBase.start_date)
        result = await self.session.scalars(query)
        return result.all()

    async def is_available(self, start: datetime, end: datetime) -> bool:
        """Return True if the requested interval has no conflicts."""
        start = _to_minsk_naive(start)
        end = _to_minsk_naive(end)

        overlap = await self.session.scalar(
            select(BookingBase).where(
                and_(
                    BookingBase.is_canceled == False,  # noqa: E712
                    BookingBase.is_done == False,  # noqa: E712
                    BookingBase.is_prepaymented == True,  # noqa: E712
                    BookingBase.start_date < end,
                    BookingBase.end_date > start,
                )
            )
        )
        return overlap is None

    # ------------------------------------------------------------------
    # Write — create
    # ------------------------------------------------------------------

    async def create_booking(self, data: BookingCreateRequest) -> BookingBase:
        """
        Create a new booking from the web wizard form.
        The booking starts as unpaid (is_prepaymented=False).
        The Telegram bot can pick it up and complete the payment flow.
        """
        start_date = _to_minsk_naive(data.checkInDate)
        end_date = _to_minsk_naive(data.checkOutDate)

        user = await self.user_repo.get_or_create_user(
            contact=data.contact,
            user_name=data.telegram or data.phone,
        )

        tariff_enum = Tariff(data.tariff_int)

        booking = BookingBase(
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            tariff=tariff_enum,
            has_photoshoot=data.hasPhotoshoot,
            has_sauna=data.hasSauna,
            has_white_bedroom=data.has_white_bedroom,
            has_green_bedroom=data.has_green_bedroom,
            has_secret_room=data.hasSecretRoom,
            has_bath_tub=data.hasBathTub,
            number_of_guests=data.guestCount,
            price=data.totalPrice,
            prepayment_price=data.prepaymentPrice
            if data.prepaymentPrice is not None
            else settings.prepayment,
            comment=data.comment,
            wine_preference=data.wine_preference_str,
            transfer_address=data.transferAddress if data.needsTransfer else None,
            is_prepaymented=False,
            source="web",
        )

        if data.promocodeId:
            booking.promocode_id = data.promocodeId

        if data.giftId:
            booking.gift_id = data.giftId
            gift = await self.session.get(GiftBase, data.giftId)
            if gift:
                gift.is_done = True

        self.session.add(booking)
        await self.session.flush()  # get booking.id

        await self.user_repo.increment_booking_count(user.id)
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    # ------------------------------------------------------------------
    # Write — manage existing bookings
    # ------------------------------------------------------------------

    async def cancel_booking(self, booking_id: int) -> BookingBase:
        """Cancel a future booking (paid or unpaid)."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        now_naive = datetime.now()
        if not (
            booking.start_date > now_naive
            and not booking.is_canceled
            and not booking.is_done
        ):
            raise ValueError("Это бронирование нельзя отменить")
        booking.is_canceled = True
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def update_tariff(
        self,
        booking_id: int,
        tariff_str: str,
        total_price: float,
    ) -> BookingBase:
        """Update the tariff and recalculated total price for a future booking."""
        from db.models.tariff import Tariff as TariffEnum
        from schemas.booking import TARIFF_ID_TO_INT

        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_can_modify(booking)

        tariff_int = TARIFF_ID_TO_INT[tariff_str]
        booking.tariff = TariffEnum(tariff_int)
        booking.price = total_price
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def update_services(
        self,
        booking_id: int,
        data: BookingUpdateServicesRequest,
    ) -> BookingBase:
        """Update additional services and recalculated total price for a future booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_can_modify(booking)

        booking.has_photoshoot = data.hasPhotoshoot
        booking.has_sauna = data.hasSauna
        booking.has_bath_tub = data.hasBathTub
        if data.bedroomType == "white":
            booking.has_white_bedroom = True
            booking.has_green_bedroom = False
        elif data.bedroomType == "green":
            booking.has_white_bedroom = False
            booking.has_green_bedroom = True
        elif data.hasExtraBedroom:
            booking.has_white_bedroom = True
            booking.has_green_bedroom = True
        booking.has_secret_room = data.hasSecretRoom
        booking.wine_preference = (
            ", ".join(data.wineSelection) if data.wineSelection else None
        )
        booking.transfer_address = data.transferAddress if data.needsTransfer else None
        booking.price = data.totalPrice
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def reschedule_booking(
        self,
        booking_id: int,
        new_start: datetime,
        new_end: datetime,
        total_price: float,
    ) -> BookingBase:
        """Reschedule a booking to new dates (only once)."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_can_modify(booking)
        if booking.is_date_changed:
            raise ValueError("Перенос даты возможен только один раз")

        new_start = _to_minsk_naive(new_start)
        new_end = _to_minsk_naive(new_end)

        if new_end <= new_start:
            raise ValueError("Дата выезда должна быть позже даты заезда")

        overlap = await self.session.scalar(
            select(BookingBase).where(
                and_(
                    BookingBase.id != booking_id,  # exclude self
                    BookingBase.is_canceled == False,  # noqa: E712
                    BookingBase.is_done == False,  # noqa: E712
                    BookingBase.is_prepaymented == True,  # noqa: E712
                    BookingBase.start_date < new_end,
                    BookingBase.end_date > new_start,
                )
            )
        )
        if overlap is not None:
            raise ValueError(
                "Выбранное время уже занято. Пожалуйста, выберите другую дату."
            )

        booking.start_date = new_start
        booking.end_date = new_end
        booking.price = total_price
        booking.is_date_changed = True
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    # ------------------------------------------------------------------
    # Admin — read all bookings
    # ------------------------------------------------------------------

    async def admin_get_all_bookings(
        self,
        sort_order: str = "desc",
        status: str = "all",
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[BookingBase], int]:
        """Return paginated bookings with user eagerly loaded, plus total count."""
        now_naive = datetime.now()

        # Build shared WHERE clause
        base = select(BookingBase)
        if status == "upcoming":
            base = base.where(
                BookingBase.start_date > now_naive,
                BookingBase.is_canceled == False,  # noqa: E712
                BookingBase.is_done == False,  # noqa: E712
            )
        elif status == "past":
            base = base.where(
                BookingBase.start_date <= now_naive,
                BookingBase.is_canceled == False,  # noqa: E712
                BookingBase.is_done == False,  # noqa: E712
            )
        elif status == "canceled":
            base = base.where(BookingBase.is_canceled == True)  # noqa: E712
        elif status == "done":
            base = base.where(BookingBase.is_done == True)  # noqa: E712
        elif status == "unpaid":
            base = base.where(
                BookingBase.is_prepaymented == False,  # noqa: E712
                BookingBase.is_canceled == False,  # noqa: E712
                BookingBase.is_done == False,  # noqa: E712
            )

        # COUNT — reuse the same filters via subquery
        count_result = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result or 0

        # Paginated fetch with eager user load
        order = (
            BookingBase.start_date.asc()
            if sort_order == "asc"
            else BookingBase.start_date.desc()
        )
        query = (
            base.options(selectinload(BookingBase.user))
            .order_by(order)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self.session.scalars(query)
        return result.all(), total

    # ------------------------------------------------------------------
    # Admin — write (bypass user restrictions)
    # ------------------------------------------------------------------

    async def admin_confirm_booking(self, booking_id: int) -> BookingBase:
        """Mark booking as prepaymented (confirmed) — admin manual override."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        if booking.is_canceled:
            raise ValueError("Нельзя подтвердить отменённое бронирование")
        if booking.is_done:
            raise ValueError("Нельзя подтвердить завершённое бронирование")
        if booking.is_prepaymented:
            raise ValueError("Бронирование уже подтверждено")
        booking.is_prepaymented = True
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def admin_cancel_booking(self, booking_id: int) -> BookingBase:
        """Cancel any non-done, non-already-cancelled booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_admin_can_modify(booking)
        booking.is_canceled = True
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def admin_update_tariff(
        self,
        booking_id: int,
        tariff_str: str,
        total_price: float,
    ) -> BookingBase:
        """Update tariff for any non-done, non-cancelled booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_admin_can_modify(booking)
        tariff_int = TARIFF_ID_TO_INT[tariff_str]
        booking.tariff = Tariff(tariff_int)
        booking.price = total_price
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def admin_update_services(
        self,
        booking_id: int,
        data: AdminUpdateServicesRequest,
    ) -> BookingBase:
        """Update additional services for any non-done, non-cancelled booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_admin_can_modify(booking)
        booking.has_photoshoot = data.hasPhotoshoot
        booking.has_sauna = data.hasSauna
        booking.has_bath_tub = data.hasBathTub
        if data.bedroomType == "white":
            booking.has_white_bedroom = True
            booking.has_green_bedroom = False
        elif data.bedroomType == "green":
            booking.has_white_bedroom = False
            booking.has_green_bedroom = True
        elif data.hasExtraBedroom:
            booking.has_white_bedroom = True
            booking.has_green_bedroom = True
        booking.has_secret_room = data.hasSecretRoom
        booking.wine_preference = (
            ", ".join(data.wineSelection) if data.wineSelection else None
        )
        booking.transfer_address = data.transferAddress if data.needsTransfer else None
        booking.price = data.totalPrice
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def admin_reschedule_booking(
        self,
        booking_id: int,
        new_start: datetime,
        new_end: datetime,
        total_price: float,
    ) -> BookingBase:
        """Reschedule booking unlimited times — does NOT set is_date_changed."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_admin_can_modify(booking)

        new_start = _to_minsk_naive(new_start)
        new_end = _to_minsk_naive(new_end)

        if new_end <= new_start:
            raise ValueError("Дата выезда должна быть позже даты заезда")

        overlap = await self.session.scalar(
            select(BookingBase).where(
                and_(
                    BookingBase.id != booking_id,
                    BookingBase.is_canceled == False,  # noqa: E712
                    BookingBase.is_done == False,  # noqa: E712
                    BookingBase.is_prepaymented == True,  # noqa: E712
                    BookingBase.start_date < new_end,
                    BookingBase.end_date > new_start,
                )
            )
        )
        if overlap is not None:
            raise ValueError(
                "Выбранное время уже занято. Пожалуйста, выберите другую дату."
            )

        booking.start_date = new_start
        booking.end_date = new_end
        booking.price = total_price
        # CRITICAL: do NOT set is_date_changed — preserves user's one reschedule privilege
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def admin_update_price(
        self,
        booking_id: int,
        total_price: float,
        prepayment_price: float,
    ) -> BookingBase:
        """Directly set price and prepayment for any non-done, non-cancelled booking."""
        booking = await self.get_by_id(booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        _assert_admin_can_modify(booking)
        booking.price = total_price
        booking.prepayment_price = prepayment_price
        await self.session.commit()
        await self.session.refresh(booking)
        return booking

    async def admin_delete_booking(self, booking_id: int) -> None:
        """Permanently delete a booking — hard delete, no restrictions."""
        booking = await self.session.get(BookingBase, booking_id)
        if not booking:
            raise ValueError("Бронирование не найдено")
        await self.session.delete(booking)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Admin — statistics
    # ------------------------------------------------------------------

    async def admin_get_statistics(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> AdminStatisticsResponse:
        """Compute comprehensive booking/user/gift statistics.

        Booking aggregations respect the optional date range (applied to start_date).
        User and gift stats are always all-time.
        """
        from datetime import time as _time

        def _apply_date_range(q):
            if from_date:
                q = q.where(BookingBase.start_date >= datetime.combine(from_date, _time.min))
            if to_date:
                q = q.where(BookingBase.start_date <= datetime.combine(to_date, _time.max))
            return q

        # ── 1. Summary ──────────────────────────────────────────────────────────
        summary_q = _apply_date_range(
            select(
                func.count().label("total"),
                func.sum(
                    case(
                        (
                            and_(
                                BookingBase.is_canceled == False,  # noqa: E712
                                BookingBase.is_done == False,  # noqa: E712
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("active"),
                func.sum(
                    case((BookingBase.is_canceled == True, 1), else_=0)  # noqa: E712
                ).label("canceled"),
                func.sum(
                    case((BookingBase.is_done == True, 1), else_=0)  # noqa: E712
                ).label("done"),
                func.sum(
                    case(
                        (BookingBase.is_canceled == False, BookingBase.price),  # noqa: E712
                        else_=0.0,
                    )
                ).label("revenue"),
                func.sum(
                    case((BookingBase.is_prepaymented == True, 1), else_=0)  # noqa: E712
                ).label("prepaid"),
            ).select_from(BookingBase)
        )
        s = (await self.session.execute(summary_q)).one()

        total = s.total or 0
        canceled = s.canceled or 0
        revenue = float(s.revenue or 0)
        non_canceled = total - canceled
        avg_price = revenue / non_canceled if non_canceled > 0 else 0.0
        cancel_rate = (canceled / total * 100) if total > 0 else 0.0

        summary = AdminStatsSummary(
            totalBookings=total,
            activeBookings=s.active or 0,
            canceledBookings=canceled,
            doneBookings=s.done or 0,
            totalRevenue=revenue,
            avgPrice=round(avg_price, 2),
            prepaidCount=s.prepaid or 0,
            cancelRate=round(cancel_rate, 1),
        )

        # ── 2. Monthly breakdown ────────────────────────────────────────────────
        year_col = extract("year", BookingBase.start_date)
        month_col = extract("month", BookingBase.start_date)
        monthly_q = _apply_date_range(
            select(
                year_col.label("yr"),
                month_col.label("mo"),
                func.count().label("total"),
                func.sum(
                    case((BookingBase.is_done == True, 1), else_=0)  # noqa: E712
                ).label("done"),
                func.sum(
                    case((BookingBase.is_canceled == True, 1), else_=0)  # noqa: E712
                ).label("canceled"),
                func.sum(
                    case(
                        (BookingBase.is_canceled == False, BookingBase.price),  # noqa: E712
                        else_=0.0,
                    )
                ).label("revenue"),
            )
            .select_from(BookingBase)
            .group_by(year_col, month_col)
            .order_by(year_col, month_col)
        )
        monthly_rows = (await self.session.execute(monthly_q)).all()
        monthly_breakdown = [
            AdminStatsMonthly(
                year=int(r.yr),
                month=int(r.mo),
                total=r.total,
                done=r.done or 0,
                canceled=r.canceled or 0,
                revenue=float(r.revenue or 0),
            )
            for r in monthly_rows
        ]

        # ── 3. Tariff breakdown ─────────────────────────────────────────────────
        revenue_expr = func.sum(
            case(
                (BookingBase.is_canceled == False, BookingBase.price),  # noqa: E712
                else_=0.0,
            )
        )
        tariff_q = _apply_date_range(
            select(
                BookingBase.tariff.label("tariff_val"),
                func.count().label("total"),
                revenue_expr.label("revenue"),
                func.sum(
                    case((BookingBase.is_canceled == True, 1), else_=0)  # noqa: E712
                ).label("canceled"),
            )
            .select_from(BookingBase)
            .group_by(BookingBase.tariff)
            .order_by(revenue_expr.desc())
        )
        tariff_rows = (await self.session.execute(tariff_q)).all()
        tariff_breakdown: list[AdminStatsTariff] = []
        for r in tariff_rows:
            tariff_int = r.tariff_val.value if hasattr(r.tariff_val, "value") else int(r.tariff_val)
            t_str = TARIFF_INT_TO_STR.get(tariff_int, "unknown")
            cancel_c = r.canceled or 0
            active_c = r.total - cancel_c
            t_avg = float(r.revenue or 0) / active_c if active_c > 0 else 0.0
            tariff_breakdown.append(
                AdminStatsTariff(
                    tariff=t_str,
                    total=r.total,
                    revenue=float(r.revenue or 0),
                    avgPrice=round(t_avg, 2),
                    cancelCount=cancel_c,
                )
            )

        # ── 4. Source breakdown ─────────────────────────────────────────────────
        src_col = func.coalesce(BookingBase.source, "unknown")
        source_q = _apply_date_range(
            select(
                src_col.label("src"),
                func.count().label("total"),
                func.sum(
                    case((BookingBase.is_done == True, 1), else_=0)  # noqa: E712
                ).label("done"),
                func.sum(
                    case((BookingBase.is_canceled == True, 1), else_=0)  # noqa: E712
                ).label("canceled"),
            )
            .select_from(BookingBase)
            .group_by(src_col)
            .order_by(func.count().desc())
        )
        source_rows = (await self.session.execute(source_q)).all()
        source_breakdown = [
            AdminStatsSource(
                source=r.src,
                total=r.total,
                done=r.done or 0,
                canceled=r.canceled or 0,
                cancelRate=round((r.canceled or 0) / r.total * 100, 1) if r.total > 0 else 0.0,
            )
            for r in source_rows
        ]

        # ── 5. Day-of-week (non-canceled) ───────────────────────────────────────
        _DOW_NAMES = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]
        pg_dow_col = extract("dow", BookingBase.start_date)
        dow_q = _apply_date_range(
            select(pg_dow_col.label("pg_dow"), func.count().label("total"))
            .select_from(BookingBase)
            .where(BookingBase.is_canceled == False)  # noqa: E712
            .group_by(pg_dow_col)
            .order_by(pg_dow_col)
        )
        dow_rows = (await self.session.execute(dow_q)).all()
        # PostgreSQL DOW: 0=Sun,1=Mon,...,6=Sat → Python weekday: 0=Mon,...,6=Sun
        dow_breakdown = sorted(
            [
                AdminStatsDow(
                    dow=(int(r.pg_dow) - 1) % 7,
                    dayName=_DOW_NAMES[(int(r.pg_dow) - 1) % 7],
                    total=r.total,
                )
                for r in dow_rows
            ],
            key=lambda x: x.dow,
        )

        # ── 6. Duration buckets (non-canceled) ──────────────────────────────────
        _DURATION_LABELS: dict[str, str] = {
            "lt_6h": "< 6 ч",
            "6_12h": "6–12 ч",
            "12_24h": "12–24 ч",
            "24_48h": "24–48 ч",
            "gt_48h": "> 48 ч",
        }
        _BUCKET_ORDER = ["lt_6h", "6_12h", "12_24h", "24_48h", "gt_48h"]
        hours_expr = (
            func.extract("epoch", BookingBase.end_date - BookingBase.start_date) / 3600.0
        )
        dur_bucket_col = case(
            (hours_expr < 6, "lt_6h"),
            (hours_expr < 12, "6_12h"),
            (hours_expr < 24, "12_24h"),
            (hours_expr < 48, "24_48h"),
            else_="gt_48h",
        )
        dur_q = _apply_date_range(
            select(dur_bucket_col.label("bucket"), func.count().label("total"))
            .select_from(BookingBase)
            .where(BookingBase.is_canceled == False)  # noqa: E712
            .group_by(dur_bucket_col)
        )
        dur_raw: dict[str, int] = {
            r.bucket: r.total for r in (await self.session.execute(dur_q)).all()
        }
        duration_breakdown = [
            AdminStatsDuration(bucket=b, label=_DURATION_LABELS[b], total=dur_raw.get(b, 0))
            for b in _BUCKET_ORDER
        ]

        # ── 7. Guest-count (non-canceled) ───────────────────────────────────────
        guest_q = _apply_date_range(
            select(
                BookingBase.number_of_guests.label("guests"),
                func.count().label("total"),
            )
            .select_from(BookingBase)
            .where(BookingBase.is_canceled == False)  # noqa: E712
            .group_by(BookingBase.number_of_guests)
            .order_by(BookingBase.number_of_guests)
        )
        guest_rows = (await self.session.execute(guest_q)).all()
        guest_count_breakdown = [
            AdminStatsGuests(guestCount=r.guests, total=r.total) for r in guest_rows
        ]

        # ── 8. Options stats (non-canceled) ─────────────────────────────────────
        opts_q = _apply_date_range(
            select(
                func.sum(
                    case((BookingBase.has_sauna == True, 1), else_=0)  # noqa: E712
                ).label("sauna"),
                func.sum(
                    case((BookingBase.has_white_bedroom == True, 1), else_=0)  # noqa: E712
                ).label("white"),
                func.sum(
                    case((BookingBase.has_green_bedroom == True, 1), else_=0)  # noqa: E712
                ).label("green"),
                func.sum(
                    case((BookingBase.has_secret_room == True, 1), else_=0)  # noqa: E712
                ).label("secret"),
                func.sum(
                    case((BookingBase.has_photoshoot == True, 1), else_=0)  # noqa: E712
                ).label("photo"),
                func.sum(
                    case((BookingBase.has_bath_tub == True, 1), else_=0)  # noqa: E712
                ).label("bath"),
                func.avg(
                    case(
                        (BookingBase.has_sauna == True, BookingBase.price),  # noqa: E712
                        else_=None,
                    )
                ).label("sauna_avg"),
                func.avg(
                    case(
                        (BookingBase.has_sauna == False, BookingBase.price),  # noqa: E712
                        else_=None,
                    )
                ).label("no_sauna_avg"),
            )
            .select_from(BookingBase)
            .where(BookingBase.is_canceled == False)  # noqa: E712
        )
        o = (await self.session.execute(opts_q)).one()
        options = AdminStatsOptions(
            hasSauna=o.sauna or 0,
            hasWhiteBedroom=o.white or 0,
            hasGreenBedroom=o.green or 0,
            hasSecretRoom=o.secret or 0,
            hasPhotoshoot=o.photo or 0,
            hasBathTub=o.bath or 0,
            saunaAvgPrice=round(float(o.sauna_avg or 0), 2),
            noSaunaAvgPrice=round(float(o.no_sauna_avg or 0), 2),
        )

        # ── 9. User stats (all-time — no date filter) ───────────────────────────
        user_q = select(
            func.count().label("total"),
            func.sum(
                case((UserBase.is_active == True, 1), else_=0)  # noqa: E712
            ).label("active"),
            func.sum(
                case((UserBase.has_bookings == True, 1), else_=0)  # noqa: E712
            ).label("with_b"),
            func.sum(
                case((UserBase.completed_bookings > 0, 1), else_=0)
            ).label("with_done"),
            func.sum(
                case((UserBase.total_bookings >= 2, 1), else_=0)
            ).label("repeat"),
            func.sum(
                case((UserBase.total_bookings >= 3, 1), else_=0)
            ).label("loyal"),
            func.sum(
                case((UserBase.chat_id.isnot(None), 1), else_=0)
            ).label("tg"),
        ).select_from(UserBase)
        u = (await self.session.execute(user_q)).one()
        users = AdminStatsUsers(
            total=u.total or 0,
            active=u.active or 0,
            withBookings=u.with_b or 0,
            withCompleted=u.with_done or 0,
            repeatCustomers=u.repeat or 0,
            loyalCustomers=u.loyal or 0,
            telegramAccounts=u.tg or 0,
        )

        # ── 10. Gift stats (all-time — no date filter) ──────────────────────────
        now_naive = datetime.now()
        gift_q = select(
            func.count().label("total"),
            func.sum(
                case((GiftBase.is_paymented == True, 1), else_=0)  # noqa: E712
            ).label("paid"),
            func.sum(
                case((GiftBase.is_done == True, 1), else_=0)  # noqa: E712
            ).label("used"),
            func.sum(
                case(
                    (
                        and_(
                            GiftBase.date_expired < now_naive,
                            GiftBase.is_done == False,  # noqa: E712
                            GiftBase.is_paymented == True,  # noqa: E712
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("expired"),
            func.avg(GiftBase.price).label("avg_price"),
        ).select_from(GiftBase)
        g = (await self.session.execute(gift_q)).one()
        gifts = AdminStatsGifts(
            total=g.total or 0,
            paid=g.paid or 0,
            used=g.used or 0,
            expired=g.expired or 0,
            avgPrice=round(float(g.avg_price or 0), 2),
        )

        return AdminStatisticsResponse(
            summary=summary,
            monthlyBreakdown=monthly_breakdown,
            tariffBreakdown=tariff_breakdown,
            sourceBreakdown=source_breakdown,
            dayOfWeekBreakdown=dow_breakdown,
            durationBreakdown=duration_breakdown,
            guestCountBreakdown=guest_count_breakdown,
            options=options,
            users=users,
            gifts=gifts,
            generatedAt=datetime.now(),
        )
