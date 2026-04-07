import sys
from loguru import logger
from config.settings import settings

# Remove default handler
logger.remove()

# Console handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
    colorize=True,
)

# File handler — rotates daily, keeps 7 days
logger.add(
    "logs/guardian_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",
    retention="7 days",
    compression="gz",
)

# Separate error log
logger.add(
    "logs/errors.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    level="ERROR",
    rotation="10 MB",
    retention="30 days",
)
