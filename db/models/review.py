from datetime import datetime

from db.models.base import Base
from sqlalchemy import DateTime, ForeignKey, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class GuestReviewBase(Base):
    __tablename__ = "guest_review"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("booking.id"), nullable=False, unique=True
    )

    rating_expectations: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_comfort: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_cleanliness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_communication: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_location: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rating_recommendation: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    liked_most: Mapped[str] = mapped_column(Text, nullable=False)
    improvement: Mapped[str] = mapped_column(Text, nullable=False)
    public_review: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"GuestReviewBase(id={self.id}, booking_id={self.booking_id})"
