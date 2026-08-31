import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.promocode import PromocodeBase
from repositories.base import BaseRepository
from schemas.booking import TARIFF_ID_TO_INT
from schemas.promocode import PromoAdminRead, PromoCreateRequest

PROMOCODE_TYPE_BOOKING_DATES = 1
PROMOCODE_TYPE_USAGE_PERIOD = 2


def _to_promo_read(p: PromocodeBase) -> PromoAdminRead:
    """Map ORM model to admin API response DTO."""
    if p.applicable_tariffs is None:
        applicable = None
    elif isinstance(p.applicable_tariffs, list):
        applicable = p.applicable_tariffs
    else:
        applicable = json.loads(p.applicable_tariffs)

    return PromoAdminRead(
        id=p.id,
        name=p.name,
        promocodeType=p.promocode_type,
        dateFrom=p.date_from,
        dateTo=p.date_to,
        discountPercentage=p.discount_percentage,
        applicableTariffs=applicable,
        isActive=p.is_active,
        createdAt=p.created_at,
    )


class PromocodeRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def validate(
        self,
        name: str,
        booking_date: date,
        tariff_str: str,
    ) -> tuple[bool, str, float, int | None]:
        """
        Validate a promocode for the given booking date and tariff.

        Returns:
            (is_valid, message, discount_percentage, promocode_id)
        """
        promo = await self.session.scalar(
            select(PromocodeBase).where(
                PromocodeBase.name == name.lower(),
                PromocodeBase.is_active == True,  # noqa: E712
            )
        )

        if not promo:
            return (False, "Промокод не найден", 0.0, None)

        today = date.today()
        tariff_int = TARIFF_ID_TO_INT.get(tariff_str)

        # Type 1: booking date must fall within promo period
        if promo.promocode_type == PROMOCODE_TYPE_BOOKING_DATES:
            if not (promo.date_from <= booking_date <= promo.date_to):
                return (
                    False,
                    "Промокод недействителен в выбранную дату бронирования",
                    0.0,
                    None,
                )

        # Type 2: current date must fall within usage period
        elif promo.promocode_type == PROMOCODE_TYPE_USAGE_PERIOD:
            if not (promo.date_from <= today <= promo.date_to):
                return (False, "Промокод недействителен в данный период", 0.0, None)

        # Tariff validation (null = all tariffs allowed)
        if promo.applicable_tariffs and tariff_int is not None:
            applicable = (
                json.loads(promo.applicable_tariffs)
                if isinstance(promo.applicable_tariffs, str)
                else promo.applicable_tariffs
            )
            if tariff_int not in applicable:
                return (
                    False,
                    "Промокод не применим к выбранному тарифу",
                    0.0,
                    None,
                )

        return (True, "Промокод применён!", promo.discount_percentage, promo.id)

    async def admin_list(self, status: str = "all") -> list[PromocodeBase]:
        """Return all promos, optionally filtered by is_active."""
        query = select(PromocodeBase)
        if status == "active":
            query = query.where(PromocodeBase.is_active == True)  # noqa: E712
        elif status == "inactive":
            query = query.where(PromocodeBase.is_active == False)  # noqa: E712
        query = query.order_by(PromocodeBase.created_at.desc())
        result = await self.session.scalars(query)
        return list(result.all())

    async def admin_get_by_id(self, promo_id: int) -> PromocodeBase | None:
        return await self.session.scalar(
            select(PromocodeBase).where(PromocodeBase.id == promo_id)
        )

    async def admin_create(self, data: PromoCreateRequest) -> PromocodeBase:
        promo = PromocodeBase(
            name=data.name,
            promocode_type=data.promocodeType,
            date_from=data.dateFrom,
            date_to=data.dateTo,
            discount_percentage=data.discountPercentage,
            applicable_tariffs=data.applicableTariffs,
            is_active=data.isActive,
        )
        self.session.add(promo)
        await self.session.commit()
        await self.session.refresh(promo)
        return promo

    async def admin_update(self, promo_id: int, data: PromoCreateRequest) -> PromocodeBase:
        promo = await self.admin_get_by_id(promo_id)
        if not promo:
            raise ValueError("Промокод не найден")
        promo.name = data.name
        promo.promocode_type = data.promocodeType
        promo.date_from = data.dateFrom
        promo.date_to = data.dateTo
        promo.discount_percentage = data.discountPercentage
        promo.applicable_tariffs = data.applicableTariffs
        promo.is_active = data.isActive
        await self.session.commit()
        await self.session.refresh(promo)
        return promo
