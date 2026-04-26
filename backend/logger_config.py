import logging
import re
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        message = record.getMessage()

        # Colorize status codes for Uvicorn access logs
        if record.name == "uvicorn.access":
            # Match status codes like " 200", " 404", etc. at the end or followed by a space
            message = re.sub(r" (2\d\d)( |$)", r" <green>\1</green>\2", message)
            message = re.sub(r" (3\d\d)( |$)", r" <yellow>\1</yellow>\2", message)
            message = re.sub(r" (4\d\d)( |$)", r" <red>\1</red>\2", message)
            message = re.sub(
                r" (5\d\d)( |$)", r" <bold><red>\1</red></bold>\2", message
            )

        logger.opt(depth=depth, exception=record.exc_info, colors=True).log(
            level, message
        )


def setup_logger():
    # Remove default handler
    logger.remove()

    # Custom format with ligatures support for Maple Mono NF CN
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>[{level}]</level> | "
        "{message}"
    )

    logger.add(
        sys.stdout, format=log_format, colorize=True, diagnose=True, backtrace=True
    )

    # Intercept standard logging (uvicorn, fastapi)
    # Set level to INFO to avoid overwhelming DEBUG logs from libraries like httpx
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    # Optional: specifically target loggers
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.level = logging.INFO
        logging_logger.propagate = False

    # Explicitly set higher level for noisy libraries
    for noisy_logger in ("httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    return logger


# Initialize logger
log = setup_logger()
