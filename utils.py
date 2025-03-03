import os
import sys

from logging_setup import get_logger

logger = get_logger(__name__)


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for cx_Freeze"""
    if getattr(sys, "frozen", False):
        # If the application is run as a bundle (cx_Freeze)
        base_path = os.path.dirname(sys.executable)
    else:
        # If the application is run from a Python interpreter
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
