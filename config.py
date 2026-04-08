import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        v = v.strip().strip('"').strip("'")
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v
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
    telegram_bot_token: str = ""
    admin_chat_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
