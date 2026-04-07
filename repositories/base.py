from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base repository that receives an injected async SQLAlchemy session."""

    def __init__(self, session: AsyncSession):
        self.session = session
