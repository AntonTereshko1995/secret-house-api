from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        v = str(v).strip().strip('"').strip("'")
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        return v
    debug: bool = False
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    prepayment: float = 80.0
    period_in_months: int = 6
    bot_receipt_url: str = ""
    bot_notify_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
