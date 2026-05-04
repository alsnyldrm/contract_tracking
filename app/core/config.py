from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Contract Tracking'
    app_env: str = 'production'
    app_host: str = '0.0.0.0'
    app_port: int = 80
    secret_key: str = '<CHANGE_ME_SECRET>'
    session_cookie_name: str = 'ct_session'
    session_expire_minutes: int = 480
    csrf_cookie_name: str = 'ct_csrf'

    db_host: str = '10.2.0.31'
    db_port: int = 5432
    db_name: str = 'ctracking'
    db_user: str = 'ctracking'
    db_password: str = ''

    timezone_default: str = 'Europe/Istanbul'

    max_upload_size_mb: int = 25
    upload_root: str = '/app/data/documents'

    log_root: str = '/app/logs'
    log_rotation_mb: int = 20
    log_retention_days: int = 30

    rate_limit_login_attempts: int = 5
    rate_limit_login_window_minutes: int = 15

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @field_validator('upload_root', 'log_root')
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return str(Path(value))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
