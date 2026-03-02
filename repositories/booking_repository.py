from datetime import date, datetime, timedelta
from typing import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from config import settings
from db.models.booking import BookingBase
from db.models.tariff import Tariff
from repositories.base import BaseRepository
from repositories.user_repository import UserRepository
from schemas.booking import BookingCreateRequest, TARIFF_ID_TO_INT


class BookingRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)
        self.user_repo = UserRepository(session)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, booking_id: int) -> BookingBase | None:
        """Return a single booking by primary key, with user eagerly loaded."""
        return self.session.scalar(
            select(BookingBase).where(BookingBase.id == booking_id)
        )

    def save_receipt_file_id(self, booking_id: int, file_id: str) -> None:
        """Persist the Telegram file_id of the payment receipt."""
        booking = self.session.get(BookingBase, booking_id)
        if booking:
            booking.receipt_file_id = file_id
            self.session.commit()

    def get_booked_periods(
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
        return self.session.scalars(query).all()

    def is_available(self, start: datetime, end: datetime) -> bool:
        """Return True if the requested interval has no conflicts."""
        # Strip timezone to match naive datetimes stored in DB
        if start.tzinfo is not None:
            start = start.replace(tzinfo=None)
        if end.tzinfo is not None:
            end = end.replace(tzinfo=None)

        overlap = self.session.scalar(
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

    def create_booking(self, data: BookingCreateRequest) -> BookingBase:
        """
        Create a new booking from the web wizard form.
        The booking starts as unpaid (is_prepaymented=False).
        The Telegram bot can pick it up and complete the payment flow.
        """
        # Normalize datetimes (strip timezone info)
        start_date = data.checkInDate.replace(tzinfo=None)
        end_date = data.checkOutDate.replace(tzinfo=None)

        user = self.user_repo.get_or_create_user(
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

        self.session.add(booking)
        self.session.flush()  # get booking.id

        self.user_repo.increment_booking_count(user.id)
        self.session.commit()
        self.session.refresh(booking)
        return booking
