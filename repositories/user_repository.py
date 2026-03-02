from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.user import UserBase
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session)

    def get_user_by_contact(self, contact: str) -> UserBase | None:
        return self.session.scalar(
            select(UserBase).where(UserBase.contact == contact)
        )

    def get_or_create_user(
        self, contact: str, user_name: str | None = None
    ) -> UserBase:
        """Return existing user or create a new one."""
        user = self.get_user_by_contact(contact)
        if user:
            return user

        user = UserBase(contact=contact, user_name=user_name)
        self.session.add(user)
        self.session.flush()  # populate user.id without committing
        return user

    def increment_booking_count(self, user_id: int) -> None:
        user = self.session.get(UserBase, user_id)
        if user:
            user.total_bookings += 1
            user.has_bookings = True
