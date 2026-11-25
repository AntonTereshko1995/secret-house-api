import logging
import secrets
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from dependencies import TelegramDep
from repositories.booking_repository import BookingRepository
from repositories.promocode_repository import PromocodeRepository
from repositories.review_repository import ReviewRepository
from schemas.review import ReviewSubmitRequest, ReviewSubmitResponse
from services.review_eligibility import review_eligibility, today_minsk

_log = logging.getLogger(__name__)
router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_session)]

REVIEW_WINDOW_CLOSED = "Отзыв для этого бронирования недоступен"
REVIEW_ALREADY_EXISTS = "Отзыв уже оставлен"
BOOKING_NOT_FOUND = "Бронирование не найдено"


def _generate_promo_code() -> str:
    return f"rev{secrets.token_hex(4)}"


@router.post(
    "", response_model=ReviewSubmitResponse, status_code=status.HTTP_201_CREATED
)
async def submit_review(
    body: ReviewSubmitRequest,
    session: DbSession,
    telegram: TelegramDep,
):
    booking_repo = BookingRepository(session)
    review_repo = ReviewRepository(session)
    promo_repo = PromocodeRepository(session)

    try:
        pub_uuid = UUID(body.bookingPublicId)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный ID бронирования",
        ) from exc

    booking = await booking_repo.get_by_public_id_with_user(pub_uuid)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=BOOKING_NOT_FOUND
        )

    if booking.feedback_submitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=REVIEW_ALREADY_EXISTS
        )

    today = today_minsk()
    can_review, _ = review_eligibility(booking, today)
    if not can_review:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=REVIEW_WINDOW_CLOSED
        )

    promo_name = _generate_promo_code()

    try:
        review = await review_repo.create(data=body, booking_id=booking.id)
        await promo_repo.create_review_reward(
            promo_name=promo_name,
            date_from=today,
            date_to=today + timedelta(days=90),
            user_id=booking.user_id,
        )
        booking.feedback_submitted = True
        booking.reward_promo_code = promo_name
        await session.commit()
    except Exception as exc:
        _log.exception("review_submit_failed: %s", exc)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Не удалось сохранить отзыв"
        ) from exc

    _log.info(
        "review_submitted id=%s booking_id=%s promo=%s",
        review.id,
        booking.id,
        promo_name,
    )

    try:
        await telegram.on_review_submitted(
            booking=booking,
            review=review,
            promo_code=promo_name.upper(),
        )
    except Exception as e:
        _log.warning("review notify failed: %s", e, exc_info=True)

    return ReviewSubmitResponse(
        ok=True,
        reviewId=review.id,
        rewardPromoCode=promo_name.upper(),
        validUntil=today + timedelta(days=90),
    )
