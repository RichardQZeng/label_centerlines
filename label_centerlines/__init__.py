import logging

from ._src import get_centerline


__version__ = "2024.7.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
