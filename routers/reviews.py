import logging
import secrets
from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from repositories.booking_repository import BookingRepository
from repositories.promocode_repository import PromocodeRepository
from repositories.review_repository import ReviewRepository
from schemas.review import ReviewSubmitRequest, ReviewSubmitResponse

_log = logging.getLogger(__name__)
router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]


def _generate_promo_code() -> str:
    return f"rev{secrets.token_hex(4)}"


@router.post("", response_model=ReviewSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_review(body: ReviewSubmitRequest, session: DbSession):
    booking_repo = BookingRepository(session)
    review_repo = ReviewRepository(session)
    promo_repo = PromocodeRepository(session)

    booking = None
    booking_id: int | None = None
    contact: str | None = body.contact

    if body.bookingPublicId:
        try:
            pub_uuid = UUID(body.bookingPublicId)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный ID бронирования",
            )
        booking = await booking_repo.get_by_public_id(pub_uuid)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Бронирование не найдено",
            )
        if booking.feedback_submitted:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Отзыв для этого бронирования уже отправлен",
            )
        booking_id = booking.id

    if not body.likedMost.strip():
        raise HTTPException(status_code=422, detail="Поле 'Что понравилось' не может быть пустым")
    if not body.improvement.strip():
        raise HTTPException(status_code=422, detail="Поле 'Что улучшить' не может быть пустым")
    if not body.publicReview.strip():
        raise HTTPException(status_code=422, detail="Поле 'Ваш отзыв' не может быть пустым")

    promo_name = _generate_promo_code()
    today = date.today()

    try:
        review = await review_repo.create(
            data=body,
            booking_id=booking_id,
            contact=contact,
            reward_promo_code=promo_name,
        )
        await promo_repo.create_review_reward(
            promo_name=promo_name,
            date_from=today,
            date_to=today + timedelta(days=90),
        )
        if booking is not None:
            booking.feedback_submitted = True
            booking.reward_promo_code = promo_name
        await session.commit()
    except Exception as exc:
        _log.exception("review_submit_failed: %s", exc)
        await session.rollback()
        raise HTTPException(status_code=500, detail="Не удалось сохранить отзыв") from exc

    _log.info("review_submitted id=%s booking_id=%s promo=%s", review.id, booking_id, promo_name)
    return ReviewSubmitResponse(ok=True, reviewId=review.id, rewardPromoCode=promo_name.upper())
