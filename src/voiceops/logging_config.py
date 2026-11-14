import logging.config

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    uvicorn_loggers = {
        name: {"handlers": [], "level": level, "propagate": True}
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
    }
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": LOG_FORMAT}},
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "standard"},
            },
            "root": {"level": level, "handlers": ["console"]},
            "loggers": uvicorn_loggers,
        }
    )
