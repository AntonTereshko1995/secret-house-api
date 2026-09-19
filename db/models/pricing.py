from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class TariffPricingBase(Base):
    __tablename__ = "tariff_pricing"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tariff_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Standard (weekend/holiday) prices
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sauna_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    bath_tub_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    secret_room_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    extra_bedroom_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    extra_hour_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    extra_people_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    photoshoot_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    multi_day_prices: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Sale (weekday) prices
    sale_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sale_sauna_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sale_bath_tub_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sale_secret_room_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    sale_extra_bedroom_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    sale_extra_hour_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    sale_extra_people_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    sale_photoshoot_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    sale_multi_day_prices: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class PricingSettingsBase(Base):
    __tablename__ = "pricing_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
