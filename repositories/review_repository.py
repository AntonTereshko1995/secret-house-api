from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.review import GuestReviewBase
from repositories.base import BaseRepository
from schemas.review import ReviewSubmitRequest


class ReviewRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(
        self,
        data: ReviewSubmitRequest,
        booking_id: int | None,
        contact: str | None,
        reward_promo_code: str,
    ) -> GuestReviewBase:
        review = GuestReviewBase(
            booking_id=booking_id,
            contact=contact,
            reward_promo_code=reward_promo_code,
            rating_expectations=data.ratingExpectations,
            rating_comfort=data.ratingComfort,
            rating_cleanliness=data.ratingCleanliness,
            rating_communication=data.ratingCommunication,
            rating_location=data.ratingLocation,
            rating_recommendation=data.ratingRecommendation,
            liked_most=data.likedMost.strip(),
            improvement=data.improvement.strip(),
            public_review=data.publicReview.strip(),
            submitted_at=datetime.now(),
        )
        self.session.add(review)
        await self.session.flush()
        return review

    async def admin_get_all(
        self, page: int = 1, page_size: int = 50
    ) -> tuple[Sequence[GuestReviewBase], int]:
        count = await self.session.scalar(
            select(func.count()).select_from(GuestReviewBase)
        ) or 0
        result = await self.session.scalars(
            select(GuestReviewBase)
            .order_by(GuestReviewBase.submitted_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return result.all(), count
