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

def format_duration(hours):
    """Convert hours to a formatted duration string.
    
    Args:
        hours (float): Duration in hours
        
    Returns:
        str: Formatted duration string (e.g., "2d 3h 30m" or "45m")
    """
    if hours == 0:
        return "0m"
        
    days = int(hours // 24)
    remaining_hours = hours % 24
    hours_part = int(remaining_hours)
    minutes = int((remaining_hours - hours_part) * 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours_part > 0:
        parts.append(f"{hours_part}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
        
    return " ".join(parts)
