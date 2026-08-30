import logging
import sys

from loguru import logger
from logtail import LogtailHandler

from config import settings


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logger() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    # Route all standard logging (uvicorn, fastapi, routers) through loguru
    logging.root.handlers = [_InterceptHandler()]
    logging.root.setLevel(logging.INFO)

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

    logger.info("BetterStack logging initialized")
