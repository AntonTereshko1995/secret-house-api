from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from repositories.pricing_repository import PricingRepository, _to_effective_record
from schemas.pricing import PublicPricingResponse

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("/pricing", response_model=PublicPricingResponse)
async def get_pricing(session: DbSession):
    """Public: returns effective tariff prices (sale or standard, decided server-side)."""
    repo = PricingRepository(session)
    rows = await repo.get_all()
    settings = await repo.get_settings()
    is_sale_active = settings.get("is_sale_active", "false") == "true"
    return PublicPricingResponse(
        tariffs=[_to_effective_record(r, is_sale_active) for r in rows],
        isSaleActive=is_sale_active,
    )
