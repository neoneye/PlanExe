"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-19
PURPOSE: Database migration runner for PlanExe - handles automatic schema updates and initialization
SRP and DRY check: Pass - Single responsibility of migration execution
"""
import os
import sys
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect
from .database import get_db, Base

def get_database_url():
    """Get database URL from environment variable"""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://planexe_user:planexe_password@localhost:5432/planexe"
    )

def run_migrations():
    """Run Alembic migrations to latest version"""
    try:
        # Set up Alembic configuration
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())

        print("🔄 Running database migrations...")

        # Check if database exists and has tables
        engine = create_engine(get_database_url())
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        if not existing_tables:
            print("📊 Database is empty, creating initial schema...")
            # Use SQLAlchemy to create tables directly for initial setup
            Base.metadata.create_all(bind=engine)

            # Mark the migration as applied
            command.stamp(alembic_cfg, "head")
            print("✅ Initial schema created successfully")
        else:
            print("📈 Database exists, applying migrations...")
            # Run migrations normally
            command.upgrade(alembic_cfg, "head")
            print("✅ Migrations completed successfully")

    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        sys.exit(1)

def create_migration(message: str):
    """Create a new migration file"""
    try:
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())

        print(f"🔄 Creating migration: {message}")
        command.revision(alembic_cfg, message=message, autogenerate=True)
        print("✅ Migration file created successfully")

    except Exception as e:
        print(f"❌ Migration creation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "create" and len(sys.argv) > 2:
            create_migration(" ".join(sys.argv[2:]))
        elif sys.argv[1] == "migrate":
            run_migrations()
        else:
            print("Usage:")
            print("  python run_migrations.py migrate")
            print("  python run_migrations.py create 'Migration message'")
    else:
        run_migrations()