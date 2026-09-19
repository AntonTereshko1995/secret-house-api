import json

from sqlalchemy import select

from db.models.pricing import PricingSettingsBase, TariffPricingBase
from repositories.base import BaseRepository
from schemas.pricing import (
    EffectiveTariffPriceRecord,
    PricingSettingsUpdateRequest,
    TariffPriceRecord,
    TariffPriceUpdateRequest,
)

TARIFF_IDS = [
    "incognito-daily",
    "incognito-12h",
    "incognito-work",
    "daily-3plus",
    "daily-couple",
    "12h-standard",
    "work-standard",
]

# Default prices mirror booking.ts TARIFF_CONFIG / TARIFF_SALE_CONFIG exactly.
DEFAULT_PRICES: dict[str, dict] = {
    "incognito-daily": {
        "price": 900,
        "sauna_price": 0,
        "bath_tub_price": 130,
        "secret_room_price": 0,
        "extra_bedroom_price": 0,
        "extra_hour_price": 30,
        "extra_people_price": 0,
        "photoshoot_price": 0,
        "multi_day_prices": {
            1: 900,
            2: 1600,
            3: 2300,
            4: 3000,
            5: 3700,
            6: 4400,
            7: 5000,
            8: 5500,
            9: 6100,
            10: 6600,
            11: 5100,
            12: 5600,
            13: 6200,
            14: 6500,
        },
        "sale_price": 700,
        "sale_sauna_price": 0,
        "sale_bath_tub_price": 130,
        "sale_secret_room_price": 0,
        "sale_extra_bedroom_price": 0,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 0,
        "sale_photoshoot_price": 0,
        "sale_multi_day_prices": {
            1: 700,
            2: 1400,
            3: 2000,
            4: 2600,
            5: 3200,
            6: 3900,
            7: 4500,
            8: 5100,
            9: 5700,
            10: 6200,
            11: 6600,
            12: 7000,
            13: 7100,
            14: 7300,
        },
    },
    "incognito-12h": {
        "price": 600,
        "sauna_price": 0,
        "bath_tub_price": 130,
        "secret_room_price": 0,
        "extra_bedroom_price": 0,
        "extra_hour_price": 30,
        "extra_people_price": 0,
        "photoshoot_price": 100,
        "multi_day_prices": {},
        "sale_price": 500,
        "sale_sauna_price": 0,
        "sale_bath_tub_price": 130,
        "sale_secret_room_price": 0,
        "sale_extra_bedroom_price": 0,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 0,
        "sale_photoshoot_price": 100,
        "sale_multi_day_prices": {},
    },
    "incognito-work": {
        "price": 450,
        "sauna_price": 0,
        "bath_tub_price": 130,
        "secret_room_price": 0,
        "extra_bedroom_price": 0,
        "extra_hour_price": 30,
        "extra_people_price": 0,
        "photoshoot_price": 100,
        "multi_day_prices": {},
        "sale_price": 400,
        "sale_sauna_price": 0,
        "sale_bath_tub_price": 130,
        "sale_secret_room_price": 0,
        "sale_extra_bedroom_price": 0,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 0,
        "sale_photoshoot_price": 100,
        "sale_multi_day_prices": {},
    },
    "daily-3plus": {
        "price": 700,
        "sauna_price": 120,
        "bath_tub_price": 180,
        "secret_room_price": 0,
        "extra_bedroom_price": 0,
        "extra_hour_price": 30,
        "extra_people_price": 0,
        "photoshoot_price": 100,
        "multi_day_prices": {
            1: 700,
            2: 1100,
            3: 1500,
            4: 1900,
            5: 2300,
            6: 2700,
            7: 3100,
            8: 3500,
            9: 3900,
            10: 4300,
            11: 4700,
            12: 5100,
            13: 5500,
            14: 5900,
        },
        "sale_price": 500,
        "sale_sauna_price": 100,
        "sale_bath_tub_price": 180,
        "sale_secret_room_price": 0,
        "sale_extra_bedroom_price": 0,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 0,
        "sale_photoshoot_price": 100,
        "sale_multi_day_prices": {
            1: 500,
            2: 950,
            3: 1400,
            4: 1800,
            5: 2200,
            6: 2600,
            7: 3000,
            8: 3400,
            9: 3700,
            10: 4000,
            11: 4300,
            12: 4500,
            13: 4800,
            14: 5000,
        },
    },
    "daily-couple": {
        "price": 500,
        "sauna_price": 120,
        "bath_tub_price": 180,
        "secret_room_price": 0,
        "extra_bedroom_price": 0,
        "extra_hour_price": 30,
        "extra_people_price": 200,
        "photoshoot_price": 100,
        "multi_day_prices": {
            1: 500,
            2: 900,
            3: 1200,
            4: 1600,
            5: 2000,
            6: 2400,
            7: 2800,
            8: 3100,
            9: 3500,
            10: 3900,
            11: 4300,
            12: 4600,
            13: 4900,
            14: 5200,
        },
        "sale_price": 400,
        "sale_sauna_price": 100,
        "sale_bath_tub_price": 180,
        "sale_secret_room_price": 0,
        "sale_extra_bedroom_price": 0,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 70,
        "sale_photoshoot_price": 100,
        "sale_multi_day_prices": {
            1: 400,
            2: 800,
            3: 1200,
            4: 1500,
            5: 1800,
            6: 2100,
            7: 2500,
            8: 2900,
            9: 3200,
            10: 3600,
            11: 3900,
            12: 4200,
            13: 4600,
            14: 4800,
        },
    },
    "12h-standard": {
        "price": 250,
        "sauna_price": 120,
        "bath_tub_price": 180,
        "secret_room_price": 70,
        "extra_bedroom_price": 70,
        "extra_hour_price": 30,
        "extra_people_price": 70,
        "photoshoot_price": 0,
        "multi_day_prices": {},
        "sale_price": 200,
        "sale_sauna_price": 100,
        "sale_bath_tub_price": 180,
        "sale_secret_room_price": 70,
        "sale_extra_bedroom_price": 70,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 70,
        "sale_photoshoot_price": 0,
        "sale_multi_day_prices": {},
    },
    "work-standard": {
        "price": 180,
        "sauna_price": 120,
        "bath_tub_price": 180,
        "secret_room_price": 50,
        "extra_bedroom_price": 50,
        "extra_hour_price": 30,
        "extra_people_price": 100,
        "photoshoot_price": 0,
        "multi_day_prices": {},
        "sale_price": 180,
        "sale_sauna_price": 100,
        "sale_bath_tub_price": 180,
        "sale_secret_room_price": 50,
        "sale_extra_bedroom_price": 50,
        "sale_extra_hour_price": 30,
        "sale_extra_people_price": 100,
        "sale_photoshoot_price": 0,
        "sale_multi_day_prices": {},
    },
}


def _parse_multi_day(raw: dict | str | None) -> dict[int, float]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    return {int(k): float(v) for k, v in raw.items()}


def _to_effective_record(row: TariffPricingBase, is_sale: bool) -> EffectiveTariffPriceRecord:
    mdp = _parse_multi_day(row.sale_multi_day_prices if is_sale else row.multi_day_prices)
    return EffectiveTariffPriceRecord(
        tariffId=row.tariff_id,
        price=row.sale_price if is_sale else row.price,
        saunaPrice=row.sale_sauna_price if is_sale else row.sauna_price,
        bathTubPrice=row.sale_bath_tub_price if is_sale else row.bath_tub_price,
        secretRoomPrice=row.sale_secret_room_price if is_sale else row.secret_room_price,
        extraBedroomPrice=row.sale_extra_bedroom_price if is_sale else row.extra_bedroom_price,
        extraHourPrice=row.sale_extra_hour_price if is_sale else row.extra_hour_price,
        extraPeoplePrice=row.sale_extra_people_price if is_sale else row.extra_people_price,
        photoshootPrice=row.sale_photoshoot_price if is_sale else row.photoshoot_price,
        multiDayPrices=mdp,
        updatedAt=row.updated_at,
    )


def _to_record(row: TariffPricingBase) -> TariffPriceRecord:
    return TariffPriceRecord(
        tariffId=row.tariff_id,
        price=row.price,
        saunaPrice=row.sauna_price,
        bathTubPrice=row.bath_tub_price,
        secretRoomPrice=row.secret_room_price,
        extraBedroomPrice=row.extra_bedroom_price,
        extraHourPrice=row.extra_hour_price,
        extraPeoplePrice=row.extra_people_price,
        photoshootPrice=row.photoshoot_price,
        multiDayPrices=_parse_multi_day(row.multi_day_prices),
        salePrice=row.sale_price,
        saleSaunaPrice=row.sale_sauna_price,
        saleBathTubPrice=row.sale_bath_tub_price,
        saleSecretRoomPrice=row.sale_secret_room_price,
        saleExtraBedroomPrice=row.sale_extra_bedroom_price,
        saleExtraHourPrice=row.sale_extra_hour_price,
        saleExtraPeoplePrice=row.sale_extra_people_price,
        salePhotoshootPrice=row.sale_photoshoot_price,
        saleMultiDayPrices=_parse_multi_day(row.sale_multi_day_prices),
        updatedAt=row.updated_at,
    )


class PricingRepository(BaseRepository):
    async def get_all(self) -> list[TariffPricingBase]:
        rows = list((await self.session.scalars(select(TariffPricingBase))).all())
        if not rows:
            rows = await self._seed_defaults()
        return rows

    async def _seed_defaults(self) -> list[TariffPricingBase]:
        for tariff_id, defaults in DEFAULT_PRICES.items():
            row = TariffPricingBase(tariff_id=tariff_id, **defaults)
            self.session.add(row)
        await self.session.commit()
        return list((await self.session.scalars(select(TariffPricingBase))).all())

    async def get_by_tariff_id(self, tariff_id: str) -> TariffPricingBase | None:
        return await self.session.scalar(
            select(TariffPricingBase).where(TariffPricingBase.tariff_id == tariff_id)
        )

    async def upsert(
        self, tariff_id: str, data: TariffPriceUpdateRequest
    ) -> TariffPricingBase:
        row = await self.get_by_tariff_id(tariff_id)
        if not row:
            row = TariffPricingBase(tariff_id=tariff_id)
            self.session.add(row)
        row.price = data.price
        row.sauna_price = data.saunaPrice
        row.bath_tub_price = data.bathTubPrice
        row.secret_room_price = data.secretRoomPrice
        row.extra_bedroom_price = data.extraBedroomPrice
        row.extra_hour_price = data.extraHourPrice
        row.extra_people_price = data.extraPeoplePrice
        row.photoshoot_price = data.photoshootPrice
        row.multi_day_prices = data.multiDayPrices
        row.sale_price = data.salePrice
        row.sale_sauna_price = data.saleSaunaPrice
        row.sale_bath_tub_price = data.saleBathTubPrice
        row.sale_secret_room_price = data.saleSecretRoomPrice
        row.sale_extra_bedroom_price = data.saleExtraBedroomPrice
        row.sale_extra_hour_price = data.saleExtraHourPrice
        row.sale_extra_people_price = data.saleExtraPeoplePrice
        row.sale_photoshoot_price = data.salePhotoshootPrice
        row.sale_multi_day_prices = data.saleMultiDayPrices
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_settings(self) -> dict[str, str]:
        rows = list((await self.session.scalars(select(PricingSettingsBase))).all())
        return {r.key: r.value for r in rows}

    async def update_settings(self, data: PricingSettingsUpdateRequest) -> None:
        for key, value in [
            ("is_sale_active", str(data.isSaleActive).lower()),
        ]:
            row = await self.session.scalar(
                select(PricingSettingsBase).where(PricingSettingsBase.key == key)
            )
            if row:
                row.value = value
            else:
                self.session.add(PricingSettingsBase(key=key, value=value))
        await self.session.commit()
