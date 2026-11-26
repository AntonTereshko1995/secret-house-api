from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.booking import BookingBase
from db.models.review import GuestReviewBase
from repositories.base import BaseRepository
from schemas.review import ReviewSubmitRequest


class ReviewRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(
        self,
        data: ReviewSubmitRequest,
        booking_id: int,
    ) -> GuestReviewBase:
        review = GuestReviewBase(
            booking_id=booking_id,
            rating_expectations=data.ratingExpectations,
            rating_comfort=data.ratingComfort,
            rating_cleanliness=data.ratingCleanliness,
            rating_communication=data.ratingCommunication,
            rating_location=data.ratingLocation,
            rating_recommendation=data.ratingRecommendation,
            liked_most=data.likedMost,
            improvement=data.improvement,
            public_review=data.publicReview,
        )
        self.session.add(review)
        await self.session.flush()
        return review

    async def get_by_id(self, review_id: int) -> GuestReviewBase | None:
        return await self.session.get(GuestReviewBase, review_id)

    async def admin_get_all(
        self,
        page: int = 1,
        page_size: int = 50,
        published: str = "all",
    ) -> tuple[Sequence[GuestReviewBase], int]:
        query = select(GuestReviewBase)
        if published == "true":
            query = query.where(GuestReviewBase.is_published == True)  # noqa: E712
        elif published == "false":
            query = query.where(GuestReviewBase.is_published == False)  # noqa: E712
        count = await self.session.scalar(
            select(func.count()).select_from(query.subquery())
        ) or 0
        result = await self.session.scalars(
            query.order_by(GuestReviewBase.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return result.all(), count

    async def public_list(
        self, limit: int
    ) -> tuple[Sequence[GuestReviewBase], dict[int, BookingBase]]:
        reviews = list(
            await self.session.scalars(
                select(GuestReviewBase)
                .where(GuestReviewBase.is_published == True)  # noqa: E712
                .order_by(GuestReviewBase.published_at.desc())
                .limit(limit)
            )
        )
        bookings: dict[int, BookingBase] = {}
        booking_ids = [r.booking_id for r in reviews]
        if booking_ids:
            rows = await self.session.scalars(
                select(BookingBase).where(BookingBase.id.in_(booking_ids))
            )
            bookings = {b.id: b for b in rows}
        return reviews, bookings

    async def public_stats(self) -> tuple[int, float]:
        """Return (total published reviews, average rating over all published)."""
        total = await self.session.scalar(
            select(func.count())
            .select_from(GuestReviewBase)
            .where(GuestReviewBase.is_published == True)  # noqa: E712
        ) or 0
        rating_sum = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        GuestReviewBase.rating_expectations
                        + GuestReviewBase.rating_comfort
                        + GuestReviewBase.rating_cleanliness
                        + GuestReviewBase.rating_communication
                        + GuestReviewBase.rating_location
                        + GuestReviewBase.rating_recommendation
                    ),
                    0,
                )
            )
            .select_from(GuestReviewBase)
            .where(GuestReviewBase.is_published == True)  # noqa: E712
        ) or 0
        average = round(rating_sum / (total * 6), 1) if total else 0.0
        return total, average

    async def set_published(
        self, review_id: int, is_published: bool
    ) -> GuestReviewBase | None:
        review = await self.get_by_id(review_id)
        if not review:
            return None
        review.is_published = is_published
        review.published_at = (
            datetime.now(timezone.utc) if is_published else None
        )
        await self.session.commit()
        await self.session.refresh(review)
        return review
