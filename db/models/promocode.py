from datetime import date, datetime

from db.models.base import Base
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column


class PromocodeBase(Base):
    __tablename__ = "promocode"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # 1 = BOOKING_DATES, 2 = USAGE_PERIOD
    promocode_type: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    discount_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    # null = ALL tariffs, or JSON array like [0, 1, 2] for specific tariff values
    applicable_tariffs: Mapped[str | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return (
            f"PromocodeBase(id={self.id}, name={self.name}, "
            f"discount={self.discount_percentage}%)"
        )
