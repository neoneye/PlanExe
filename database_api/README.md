# database_api

Shared database models used by multiple PlanExe services (e.g., `frontend_multiuser`, future `worker_plan_database`). Models live here to keep them out of `worker_plan_api`, which stays worker-focused and lightweight.

## Contents
- `model_event.py`: `EventType` enum and `EventItem` SQLAlchemy model.
- `model_taskitem.py`: `TaskState` enum and `TaskItem` SQLAlchemy model.
- `model_worker.py`: `WorkerItem` SQLAlchemy model for worker heartbeats.
- `model_nonce.py`: `NonceItem` SQLAlchemy model for nonce tracking.

## How to import
Add the repo root (containing `database_api/`) to `PYTHONPATH`, then:
```python
from database_api.planexe_db_singleton import db
from database_api.model_event import EventType, EventItem
from database_api.model_taskitem import TaskItem, TaskState
from database_api.model_worker import WorkerItem
from database_api.model_nonce import NonceItem
```

Each model expects a `db` instance to be available in the module namespace (e.g., via `from database_api.planexe_db_singleton import db` in your service). Keep the models as-is to avoid divergence across services.
