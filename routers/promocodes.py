from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_session
from repositories.promocode_repository import PromocodeRepository
from schemas.promocode import PromoValidateRequest, PromoValidateResponse

router = APIRouter()

DbSession = Annotated[Session, Depends(get_session)]


@router.post("/validate", response_model=PromoValidateResponse)
def validate_promocode(body: PromoValidateRequest, session: DbSession):
    """
    Validate a promocode for the given booking date and tariff.
    Returns validity, discount percentage, and a user-facing message.
    """
    repo = PromocodeRepository(session)
    is_valid, message, discount_pct, promo_id = repo.validate(
        name=body.code,
        booking_date=body.bookingDate,
        tariff_str=body.tariff,
    )

    return PromoValidateResponse(
        valid=is_valid,
        discountPercentage=discount_pct if is_valid else 0.0,
        # Return 0 for the BYN amount — frontend calculates it from percentage
        discount=0.0,
        message=message,
        promocodeId=promo_id,
    )
