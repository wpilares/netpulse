import logging

import uvicorn

from netpulse_api.app import create_app
from netpulse_api.health import PostgresProbe
from netpulse_api.settings import ApiSettings


def main() -> None:
    settings = ApiSettings()
    logging.basicConfig(level=settings.log_level)
    probe = (
        PostgresProbe(
            settings.database_url.encoded_string(),
            timeout_seconds=settings.database_timeout_seconds,
        )
        if settings.database_url is not None
        else None
    )
    uvicorn.run(
        create_app(database_probe=probe),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
