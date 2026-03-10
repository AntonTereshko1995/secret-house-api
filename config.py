import os
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


class Settings(BaseSettings):
    database_url: str = _get_database_url()
    debug: bool = False
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    prepayment: float = 80.0
    period_in_months: int = 6
    bot_base_url: str = ""

    @property
    def bot_receipt_url(self) -> str:
        return f"{self.bot_base_url.rstrip('/')}/api/receipt" if self.bot_base_url else ""

    @property
    def bot_notify_url(self) -> str:
        return f"{self.bot_base_url.rstrip('/')}/api/new-booking" if self.bot_base_url else ""
    better_stack_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
