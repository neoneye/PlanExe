"""
Flask application for editing plans with a DAG and markdown panel.
Currently exposes the factory function in planexe.edit.app.
"""

from .app import create_app  # noqa: F401
