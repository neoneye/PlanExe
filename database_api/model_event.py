"""
Register events in the database.
So I don't have to look through the logs to find out what happened.
"""
import logging
import enum
from typing import Optional
from datetime import datetime, UTC
from planexe_db_singleton import db
from sqlalchemy import JSON, Text

logger = logging.getLogger(__name__)

class EventType(enum.Enum):
    GENERIC_ERROR = "generic_error"
    GENERIC_EVENT = "generic_event"
    TASK_PENDING = "task_pending"
    TASK_PROCESSING = "task_processing"
    TASK_FAILED = "task_failed"
    TASK_COMPLETED = "task_completed"

class EventItem(db.Model):
    __tablename__ = 'events'

    # A unique identifier for the event.
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # When was the event logged.
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    
    # Overarching type of event.
    event_type = db.Column(db.Enum(EventType), nullable=False, index=True)

    # A short message describing the event.
    message = db.Column(Text, nullable=False)
    
    # Info about the event, such as path to the report file, or the uuid of the task.
    context = db.Column(JSON, nullable=True, default=None)

    def __repr__(self):
        return f"<EventItem(id={self.id}, type='{self.event_type!r}', ts='{self.timestamp}', msg='{self.message[:50]}...')>"

    @classmethod
    def demo_items(cls) -> list['EventItem']:
        event1 = EventItem(
            event_type=EventType.GENERIC_EVENT,
            message="DEMO: Flask application started successfully.",
            context={"host": "0.0.0.0", "port": 5000, "environment": "development"}
        )
        event2 = EventItem(
            event_type=EventType.GENERIC_ERROR,
            message="DEMO: Cannot connect to the database without context.",
            context=None
        )
        event3 = EventItem(
            event_type=EventType.GENERIC_ERROR,
            message="DEMO: Cannot connect to the database with context.",
            context={"key": "value"}
        )
        event4 = EventItem(
            event_type=EventType.TASK_FAILED,
            message="DEMO: Unable to generate report.",
            context={"task_id": "1234567890", "error_code": "FileNotFound", "error_details": "Source data file '/mnt/data/source.csv' not found."}
        )
        event5 = EventItem(
            event_type=EventType.TASK_COMPLETED,
            message="DEMO: Report generation completed successfully.",
            context={"task_id": "1234567890", "report_path": "/reports/final_report_20231026.pdf", "duration_seconds": 125.5}
        )
        event6 = EventItem(
            event_type=EventType.TASK_PROCESSING,
            message="DEMO: Task is being processed.",
            context={"time_between_pending_and_processing": 10.0}
        )
        event7 = EventItem(
            event_type=EventType.TASK_PENDING,
            message="DEMO: /run endpoint created a pending task.",
            context={"task_id": "1234567890"}
        )
        return [event1, event2, event3, event4, event5, event6, event7]
