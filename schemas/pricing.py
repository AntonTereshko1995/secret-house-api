from datetime import datetime

from pydantic import BaseModel, field_validator


class TariffPriceRecord(BaseModel):
    tariffId: str
    # Standard prices
    price: float
    saunaPrice: float
    bathTubPrice: float
    secretRoomPrice: float
    extraBedroomPrice: float
    extraHourPrice: float
    extraPeoplePrice: float
    photoshootPrice: float
    combinedSaunaBathTubPrice: float
    multiDayPrices: dict[int, float]
    # Sale prices
    salePrice: float
    saleSaunaPrice: float
    saleBathTubPrice: float
    saleSecretRoomPrice: float
    saleExtraBedroomPrice: float
    saleExtraHourPrice: float
    saleExtraPeoplePrice: float
    salePhotoshootPrice: float
    saleCombinedSaunaBathTubPrice: float
    saleMultiDayPrices: dict[int, float]
    updatedAt: datetime


class EffectiveTariffPriceRecord(BaseModel):
    """Effective prices resolved by the backend — either standard or sale, never both."""
    tariffId: str
    price: float
    saunaPrice: float
    bathTubPrice: float
    secretRoomPrice: float
    extraBedroomPrice: float
    extraHourPrice: float
    extraPeoplePrice: float
    photoshootPrice: float
    combinedSaunaBathTubPrice: float
    multiDayPrices: dict[int, float]
    updatedAt: datetime


class PublicPricingResponse(BaseModel):
    tariffs: list[EffectiveTariffPriceRecord]
    isSaleActive: bool
    isSaunaBathTubComboActive: bool


class PricingResponse(BaseModel):
    tariffs: list[TariffPriceRecord]
    isSaleActive: bool
    isSaunaBathTubComboActive: bool


class TariffPriceUpdateRequest(BaseModel):
    price: float
    saunaPrice: float
    bathTubPrice: float
    secretRoomPrice: float
    extraBedroomPrice: float
    extraHourPrice: float
    extraPeoplePrice: float
    photoshootPrice: float
    combinedSaunaBathTubPrice: float
    multiDayPrices: dict[int, float]
    salePrice: float
    saleSaunaPrice: float
    saleBathTubPrice: float
    saleSecretRoomPrice: float
    saleExtraBedroomPrice: float
    saleExtraHourPrice: float
    saleExtraPeoplePrice: float
    salePhotoshootPrice: float
    saleCombinedSaunaBathTubPrice: float
    saleMultiDayPrices: dict[int, float]

    @field_validator(
        "price",
        "salePrice",
        "saunaPrice",
        "saleSaunaPrice",
        "bathTubPrice",
        "saleBathTubPrice",
        "extraHourPrice",
        "saleExtraHourPrice",
        "combinedSaunaBathTubPrice",
        "saleCombinedSaunaBathTubPrice",
        mode="before",
    )
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Цена не может быть отрицательной")
        return v


class PricingSettingsUpdateRequest(BaseModel):
    isSaleActive: bool
    isSaunaBathTubComboActive: bool


class PricingUpdateResponse(BaseModel):
    tariffId: str
    message: str
