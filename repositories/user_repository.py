from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import UserBase
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_user_by_contact(self, contact: str) -> UserBase | None:
        return await self.session.scalar(
            select(UserBase).where(UserBase.contact == contact)
        )

    async def get_or_create_user(
        self, contact: str, user_name: str | None = None
    ) -> UserBase:
        """Return existing user or create a new one."""
        user = await self.get_user_by_contact(contact)
        if user:
            return user

        user = UserBase(contact=contact, user_name=user_name)
        self.session.add(user)
        await self.session.flush()  # populate user.id without committing
        return user

    async def increment_booking_count(self, user_id: int) -> None:
        user = await self.session.get(UserBase, user_id)
        if user:
            user.total_bookings += 1
            user.has_bookings = True
