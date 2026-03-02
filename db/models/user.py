from db.models.base import Base
from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class UserBase(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contact: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String, nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    has_bookings: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_bookings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_bookings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"UserBase(id={self.id}, user_name={self.user_name}, contact={self.contact})"
