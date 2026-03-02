from sqlalchemy.orm import Session


class BaseRepository:
    """Base repository that receives an injected SQLAlchemy session."""

    def __init__(self, session: Session):
        self.session = session
