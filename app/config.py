from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_password: str
    session_secret: str
    printer_ip: str
    print_rate_limit_per_hour: int = 10
    page_size: str = "letter"
    database_path: str = "./data/kiosk.db"
    images_dir: str = "./data/images"


@lru_cache
def get_settings() -> Settings:
    return Settings()
