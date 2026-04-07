from datetime import date, datetime
from typing import Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.models.booking import BookingBase
from db.models.gift import GiftBase
from db.models.tariff import Tariff
from repositories.base import BaseRepository
from repositories.user_repository import UserRepository
from schemas.booking import BookingCreateRequest


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
                BookingBase.is_canceled == False,      # noqa: E712
                BookingBase.is_done == False,          # noqa: E712
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

    async def is_available(self, start: datetime, end: datetime) -> bool:
        """Return True if the requested interval has no conflicts."""
        if start.tzinfo is not None:
            start = start.replace(tzinfo=None)
        if end.tzinfo is not None:
            end = end.replace(tzinfo=None)

        overlap = await self.session.scalar(
            select(BookingBase).where(
                and_(
                    BookingBase.is_canceled == False,      # noqa: E712
                    BookingBase.is_done == False,          # noqa: E712
                    BookingBase.is_prepaymented == True,   # noqa: E712
                    BookingBase.start_date < end,
                    BookingBase.end_date > start,
                )
            )
        )
        return overlap is None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create_booking(self, data: BookingCreateRequest) -> BookingBase:
        """
        Create a new booking from the web wizard form.
        The booking starts as unpaid (is_prepaymented=False).
        The Telegram bot can pick it up and complete the payment flow.
        """
        start_date = data.checkInDate.replace(tzinfo=None)
        end_date = data.checkOutDate.replace(tzinfo=None)

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
            number_of_guests=data.guestCount,
            price=data.totalPrice,
            prepayment_price=data.prepaymentPrice or settings.prepayment,
            comment=data.comment,
            wine_preference=data.wine_preference_str,
            transfer_address=data.transferAddress if data.needsTransfer else None,
            is_prepaymented=False,
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
