import logging
from typing import Final, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

HTTP_CLIENT_LOGGER: Final = "httpx2"


def quiet_http_client_logging() -> None:
    logging.getLogger(HTTP_CLIENT_LOGGER).setLevel(logging.WARNING)


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="ignore")

    log_level: LogLevel = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value
