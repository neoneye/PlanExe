"""
This module provides a centralized SQLAlchemy database instance for the Flask application.

The database instance is imported and used across multiple files:
- app.py: For initializing Flask-SQLAlchemy and creating database tables
- models.py: For defining database models and their relationships

This pattern helps avoid circular imports and maintains a clean separation of concerns
in the Flask application architecture. The single database instance ensures that all
parts of the application work with the same database connection.
"""

from flask_sqlalchemy import SQLAlchemy

# Create a single SQLAlchemy instance to be shared across the application
db = SQLAlchemy() 