"""
Custom ModelViews for the PlanExe-server tables.
"""
from flask_admin.contrib.sqla import ModelView

class WorkerItemView(ModelView):
    """Custom ModelView for WorkerItem"""
    column_list = ['id', 'started_at', 'last_heartbeat_at', 'current_task_id']
    column_default_sort = ('id', False)
    column_searchable_list = ['id', 'current_task_id']
    column_filters = ['started_at', 'last_heartbeat_at']

class TaskItemView(ModelView):
    """Custom ModelView for TaskItem"""
    column_list = ['id', 'timestamp_created', 'state', 'prompt', 'progress_percentage', 'progress_message', 'user_id', 'parameters']
    column_default_sort = ('timestamp_created', False)  # Sort by creation timestamp, newest first
    column_searchable_list = ['id', 'prompt', 'user_id']
    column_filters = ['state', 'timestamp_created', 'user_id']
    column_formatters = {
        'id': lambda v, c, m, p: str(m.id)[:8] if m.id else '',
        'prompt': lambda v, c, m, p: m.prompt[:100] + '...' if m.prompt and len(m.prompt) > 100 else m.prompt
    }

class NonceItemView(ModelView):
    """Custom ModelView for NonceItem"""
    def __init__(self, model, *args, **kwargs):
        self.column_list = [c.key for c in model.__table__.columns]
        self.form_columns = self.column_list
        super(NonceItemView, self).__init__(model, *args, **kwargs)
        
    column_default_sort = ('created_at', True)
    column_searchable_list = ['nonce_key']
    column_filters = ['request_count', 'created_at', 'last_accessed_at']

    def get_create_form(self):
        form = self.scaffold_form()
        delattr(form, 'id')
        return form
