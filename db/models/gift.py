from datetime import datetime

from db.models.base import Base
from db.models.decorator.type_decorator import IntEnumType
from db.models.tariff import Tariff
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class GiftBase(Base):
    __tablename__ = "gift"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    buyer_contact: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    date_expired: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tariff: Mapped[Tariff] = mapped_column(IntEnumType(Tariff), nullable=False)
    has_sauna: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_additional_bedroom: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    has_secret_room: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_paymented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    code: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)

    user = relationship("UserBase")

    def __repr__(self) -> str:
        return f"GiftBase(id={self.id}, code={self.code}, expired={self.date_expired})"
