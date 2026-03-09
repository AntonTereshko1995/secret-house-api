import logging
import sys

from loguru import logger
from logtail import LogtailHandler

from config import settings


def setup_logger() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    if not settings.better_stack_token:
        logger.warning("BETTER_STACK_TOKEN not set — remote logging disabled")
        return

    logtail_handler = LogtailHandler(source_token=settings.better_stack_token)

    # Bridge loguru → BetterStack
    class LogtailSink:
        def write(self, message: str) -> None:
            record = message.record  # type: ignore[attr-defined]
            level_map = {
                "TRACE": logging.DEBUG,
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "SUCCESS": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            log_record = logging.LogRecord(
                name=record["name"],
                level=level_map.get(record["level"].name, logging.INFO),
                pathname=record["file"].path,
                lineno=record["line"],
                msg=record["message"],
                args=[],
                exc_info=record["exception"],
            )
            logtail_handler.emit(log_record)

    logger.add(LogtailSink().write, level="INFO", format="{message}")

    # Bridge uvicorn standard logging → BetterStack
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logging.getLogger(name).addHandler(logtail_handler)
        logging.getLogger(name).setLevel(logging.INFO)

    logger.info("BetterStack logging initialized")
