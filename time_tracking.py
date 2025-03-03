import sqlite3
from datetime import datetime

from alchemy import create_task, get_db_connection, get_task, update_task
from logging_setup import get_logger

logger = get_logger(__name__)


def start_task(task_name, jira_key=None, notes=None):
    """Start a new task and return its ID"""
    try:
        task_id = create_task(task_name, jira_key, notes)
        start_time = datetime.now().isoformat()
        update_task(task_id, start_time=start_time)
        logger.info(f"Started task: {task_name} (ID: {task_id})")
        return task_id
    except Exception as e:
        logger.error(f"Error starting task: {e}")
        raise


def pause_task(task_id):
    """Pause a running task and update its duration"""
    try:
        task = get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        start_time = datetime.fromisoformat(task[2]) if task[2] else None
        if not start_time:
            raise ValueError(f"Task {task_id} hasn't been started")

        end_time = datetime.now()
        new_duration = calculate_duration(start_time, end_time)
        total_duration = (task[4] or 0) + new_duration

        update_task(task_id, end_time=end_time.isoformat(), duration=total_duration)
        logger.info(f"Paused task {task_id}")
        return total_duration
    except Exception as e:
        logger.error(f"Error pausing task: {e}")
        raise


def resume_task(task_id):
    """Resume a paused task"""
    try:
        task = get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        start_time = datetime.now().isoformat()
        update_task(task_id, start_time=start_time, end_time=None)
        logger.info(f"Resumed task {task_id}")
    except Exception as e:
        logger.error(f"Error resuming task: {e}")
        raise


def stop_task(task_id):
    """Stop a task and finalize its duration"""
    try:
        task = get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        start_time = datetime.fromisoformat(task[2]) if task[2] else None
        if not start_time:
            raise ValueError(f"Task {task_id} hasn't been started")

        # Calculate final duration including any previous duration
        end_time = datetime.now()
        new_duration = calculate_duration(start_time, end_time)
        total_duration = (task[4] or 0) + new_duration

        update_task(task_id, end_time=end_time.isoformat(), duration=total_duration)
        logger.info(f"Stopped task {task_id}")
        return total_duration
    except Exception as e:
        logger.error(f"Error stopping task: {e}")
        raise


def calculate_duration(start_time, end_time) -> float:
    """
    Calculate duration in hours between start and end times

    Args:
        start_time: Start time (datetime object or string in isoformat)
        end_time: End time (datetime object or string in isoformat)

    Returns:
        float: Duration in hours
    """
    if not start_time or not end_time:
        return 0.0

    if isinstance(start_time, str):
        start = datetime.fromisoformat(start_time)
    else:
        start = start_time

    if isinstance(end_time, str):
        end = datetime.fromisoformat(end_time)
    else:
        end = end_time

    duration = end - start
    return duration.total_seconds() / 3600  # Convert to hours
