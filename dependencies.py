"""FastAPI dependency factories for shared services."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from config import settings
from services.telegram_service import TelegramService


@lru_cache(maxsize=1)
def get_telegram_service() -> TelegramService:
    return TelegramService(bot_base_url=settings.bot_base_url)


TelegramDep = Annotated[TelegramService, Depends(get_telegram_service)]
