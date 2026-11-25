from datetime import date

from pydantic import BaseModel, Field, field_validator


class ReviewSubmitRequest(BaseModel):
    bookingPublicId: str

    ratingExpectations: int = Field(ge=1, le=10)
    ratingComfort: int = Field(ge=1, le=10)
    ratingCleanliness: int = Field(ge=1, le=10)
    ratingCommunication: int = Field(ge=1, le=10)
    ratingLocation: int = Field(ge=1, le=10)
    ratingRecommendation: int = Field(ge=1, le=10)

    likedMost: str
    improvement: str
    publicReview: str

    @field_validator("likedMost", "improvement", "publicReview")
    @classmethod
    def non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Поле не может быть пустым")
        return v


class ReviewSubmitResponse(BaseModel):
    ok: bool
    reviewId: int
    rewardPromoCode: str
    validUntil: date
