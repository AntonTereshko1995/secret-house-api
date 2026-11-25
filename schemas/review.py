from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ReviewSubmitRequest(BaseModel):
    bookingPublicId: Optional[str] = None
    contact: Optional[str] = None

    ratingExpectations: int = Field(ge=1, le=10)
    ratingComfort: int = Field(ge=1, le=10)
    ratingCleanliness: int = Field(ge=1, le=10)
    ratingCommunication: int = Field(ge=1, le=10)
    ratingLocation: int = Field(ge=1, le=10)
    ratingRecommendation: int = Field(ge=1, le=10)

    likedMost: str
    improvement: str
    publicReview: str

    @model_validator(mode="after")
    def require_booking_or_contact(self) -> "ReviewSubmitRequest":
        if not self.bookingPublicId and not self.contact:
            raise ValueError("Укажите ID бронирования или контакт")
        return self


class ReviewSubmitResponse(BaseModel):
    ok: bool
    reviewId: int
    rewardPromoCode: str
