import os
import shutil
import sys
import tempfile

from logging_setup import get_logger

logger = get_logger(__name__)


def ensure_file_exists(source_path, dest_path):
    """Ensure file exists in destination, copying from source if needed"""
    if not os.path.exists(dest_path):
        try:
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            # Copy the file from the bundled resources
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            logger.error(f"Error copying file {source_path} to {dest_path}: {e}")


def resource_path(relative_path):
    """Get absolute path to resource, works for dev, PyInstaller and cx_Freeze"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        if getattr(sys, "frozen", False):
            # If the application is run as a bundle (cx_Freeze)
            base_path = os.path.dirname(sys.executable)
        else:
            # If the application is run from a Python interpreter
            base_path = os.path.abspath(".")

    # For writable files, use the user's temp directory
    writable_files = ["tasks_new.json", ".env", "timetracker.db"]
    if relative_path in writable_files:
        temp_dir = os.path.join(tempfile.gettempdir(), "TimeTracker")
        os.makedirs(temp_dir, exist_ok=True)
        dest_path = os.path.join(temp_dir, relative_path)

        # For tasks_new.json, ensure it exists in temp directory
        if relative_path == "tasks_new.json":
            source_path = os.path.join(base_path, relative_path)
            ensure_file_exists(source_path, dest_path)

        return dest_path

    # For static files (images, etc.)
    if relative_path.startswith("static/"):
        return os.path.join(base_path, relative_path)

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
