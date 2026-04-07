import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.promocode import PromocodeBase
from repositories.base import BaseRepository
from schemas.booking import TARIFF_ID_TO_INT

PROMOCODE_TYPE_BOOKING_DATES = 1
PROMOCODE_TYPE_USAGE_PERIOD = 2


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
