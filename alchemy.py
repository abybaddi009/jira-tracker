import logging
from datetime import datetime

from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from logging_setup import get_logger

logger = get_logger(__name__)

Base = declarative_base()
engine = create_engine("sqlite:///timetracker.db")
Session = sessionmaker(bind=engine)


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True)
    task_name = Column(String, nullable=False)
    start_time = Column(String)
    end_time = Column(String)
    duration = Column(Float)
    jira_key = Column(String)
    created_date = Column(String, nullable=False)
    task_id_required = Column(Integer, default=0)
    synced = Column(Integer, default=0)
    notes = Column(Text)
    worklog_id = Column(Integer)


def get_db_connection():
    """Create and return a database session"""
    return Session()


def init_db():
    """Initialize the database and create the tasks table if it doesn't exist"""
    try:
        Base.metadata.create_all(engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def create_task(task_name, jira_key=None, notes=None):
    """Create a new task and return its ID"""
    try:
        session = Session()
        new_task = Task(
            task_name=task_name,
            created_date=datetime.now().isoformat(),
            jira_key=jira_key,
            notes=notes,
        )
        session.add(new_task)
        session.commit()
        task_id = new_task.task_id
        session.close()
        logger.info(f"Created new task: {task_name}")
        return task_id
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise


def get_tasks_for_today():
    """Retrieve all tasks for today"""
    try:
        session = Session()
        today = datetime.now().date().isoformat()
        tasks = (
            session.query(Task)
            .filter(Task.created_date.like(f"{today}%"))
            .order_by(Task.task_id.desc())
            .all()
        )
        session.close()
        return tasks
    except Exception as e:
        logger.error(f"Error retrieving today's tasks: {e}")
        raise


def update_task(task_id, **kwargs):
    """Update task fields"""
    valid_fields = {
        "task_name",
        "start_time",
        "end_time",
        "duration",
        "jira_key",
        "synced",
        "notes",
        "worklog_id",
    }

    update_fields = {k: v for k, v in kwargs.items() if k in valid_fields}
    if not update_fields:
        return

    try:
        session = Session()
        task = session.query(Task).filter_by(task_id=task_id).first()
        for key, value in update_fields.items():
            setattr(task, key, value)
        session.commit()
        session.close()
        logger.info(f"Updated task {task_id}")
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise


def get_task(task_id):
    """Retrieve a specific task by ID"""
    try:
        session = Session()
        task = session.query(Task).filter_by(task_id=task_id).first()
        session.close()
        if task:
            return (
                task.task_id,
                task.task_name,
                task.start_time,
                task.end_time,
                task.duration,
                task.jira_key,
                task.created_date,
                task.task_id_required,
                task.synced,
                task.notes,
                task.worklog_id,
            )
        return None
    except Exception as e:
        logger.error(f"Error retrieving task: {e}")
        raise


def get_tasks_for_date(date):
    """Retrieve all tasks for a specific date"""
    try:
        session = Session()
        tasks = (
            session.query(Task)
            .filter(Task.created_date.like(f"{date.isoformat()}%"))
            .order_by(Task.task_id.desc())
            .all()
        )
        session.close()
        return tasks
    except Exception as e:
        logger.error(f"Error retrieving tasks for date {date}: {e}")
        raise


def delete_tasks(task_ids):
    """Delete multiple tasks by their IDs"""
    try:
        session = Session()
        session.query(Task).filter(Task.task_id.in_(task_ids)).delete(
            synchronize_session=False
        )
        session.commit()
        session.close()
        logger.info(f"Deleted tasks: {task_ids}")
    except Exception as e:
        logger.error(f"Error deleting tasks: {e}")
        raise
