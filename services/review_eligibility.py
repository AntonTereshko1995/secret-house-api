"""Single source of truth for the guest-review window rule.

Every caller that needs to know whether a booking can be reviewed must use
``review_eligibility``. The bot repeats this rule only for an early refusal,
but the API remains the source of truth.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from db.models.booking import BookingBase

_MINSK_TZ = ZoneInfo("Europe/Minsk")

REVIEW_WINDOW_DAYS = 14


def today_minsk() -> date:
    """Return the current date in Minsk (Europe/Minsk)."""
    return datetime.now(_MINSK_TZ).date()


def review_eligibility(
    booking: BookingBase, today: date
) -> tuple[bool, date | None]:
    """Decide whether a booking can be reviewed and return the last window day.

    Returns ``(can_review, deadline)`` where ``deadline`` is
    ``start_date.date() + 14 days`` (the last day, inclusive). The window is
    open only for a non-cancelled, prepaid booking without a review, when
    ``today`` is within ``[start_date.date(); deadline]`` inclusive.
    """
    deadline = booking.start_date.date() + timedelta(days=REVIEW_WINDOW_DAYS)
    can_review = (
        not booking.is_canceled
        and booking.is_prepaymented
        and not booking.feedback_submitted
        and booking.start_date.date() <= today <= deadline
    )
    return can_review, deadline
