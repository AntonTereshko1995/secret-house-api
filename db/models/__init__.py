# Import all models here so SQLAlchemy can resolve relationship() references
# before any mapper is configured or query is executed.
from db.models.base import Base  # noqa: F401
from db.models.user import UserBase  # noqa: F401
from db.models.gift import GiftBase  # noqa: F401
from db.models.promocode import PromocodeBase  # noqa: F401
from db.models.booking import BookingBase  # noqa: F401
