# model_worker.py
from datetime import datetime, UTC
from typing import Optional
import logging

from planexe_db_singleton import db # Assuming your db instance is here

logger = logging.getLogger(__name__)

class WorkerItem(db.Model):
    __tablename__ = 'workers'

    # The unique ID for the worker (e.g., from PLANEXE_WORKER_ID environment variable), eg. `PLANEXE_WORKER_ID=42`
    # If no PLANEXE_WORKER_ID is set, the worker_id is assigned a random UUID.
    id = db.Column(db.String(255), primary_key=True)
    
    # Timestamp when this worker record was first created/registered
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))
    
    # Timestamp of the last heartbeat received from this worker
    last_heartbeat_at = db.Column(db.DateTime, nullable=False, index=True, default=lambda: datetime.now(UTC))
    
    # The ID (UUID string) of the TaskItem this worker is currently processing, if any
    current_task_id = db.Column(db.String(255), nullable=True, index=True) 

    def __repr__(self):
        return (f"<WorkerItem(id='{self.id}', "
                f"last_heartbeat='{self.last_heartbeat_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.last_heartbeat_at else 'N/A'}', "
                f"task='{self.current_task_id if self.current_task_id else 'None'}')>")

    @classmethod
    def upsert_heartbeat(cls, worker_id: str, current_task_id: Optional[str] = None):
        """
        Registers a new worker or updates an existing worker's heartbeat 
        and the task it's currently working on.
        """
        now_utc = datetime.now(UTC)
        
        # Try to get existing worker
        worker = db.session.get(cls, worker_id)
        
        if worker:
            # Update existing worker
            worker.last_heartbeat_at = now_utc
            worker.current_task_id = current_task_id
            logger.debug(f"Worker {worker_id}: Heartbeat updated. Current task: {current_task_id!r}")
        else:
            # Create new worker record
            worker = WorkerItem(
                id=worker_id,
                started_at=now_utc,
                last_heartbeat_at=now_utc,
                current_task_id=current_task_id
            )
            db.session.add(worker)
            logger.info(f"Worker {worker_id}: Registered. Current task: {current_task_id!r}")
        
        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Worker {worker_id}: Database error during heartbeat upsert: {e}", exc_info=True)
            db.session.rollback()
