"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-19
PURPOSE: Database models and connection for PlanExe API - provides persistent storage for plans and LLM interactions
SRP and DRY check: Pass - Single responsibility of data persistence layer, DRY database operations
"""
import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, Float, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Database URL from environment variable - default to SQLite for development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./planexe.db"
)

# CRITICAL FIX: Add connection timeout and health checks to prevent Luigi worker thread deadlock
# Without these, SQLAlchemy will hang indefinitely trying to connect to unreachable PostgreSQL
# This was causing luigi.build() to hang for 30+ seconds without executing any tasks
engine_kwargs = {
    "pool_pre_ping": True,  # Test connections before using them (detect dead connections)
    "pool_recycle": 3600,   # Recycle connections after 1 hour
    "connect_args": {
        "connect_timeout": 10  # 10 second connection timeout (PostgreSQL and SQLite compatible)
    }
}

# SQLite doesn't support all PostgreSQL connection args
if DATABASE_URL.startswith("sqlite"):
    # SQLite timeout is in milliseconds (different from PostgreSQL!)
    engine_kwargs["connect_args"] = {"timeout": 10.0}  # 10 seconds

# Create engine with timeout and connection health checks
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Plan(Base):
    """Database model for storing plan information and progress"""
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=True)  # For multi-user support

    # Plan configuration
    prompt = Column(Text, nullable=False)
    llm_model = Column(String(255), nullable=True)
    speed_vs_detail = Column(String(50), nullable=False, default="ALL_DETAILS_BUT_SLOW")
    openrouter_api_key_hash = Column(String(255), nullable=True)  # Hashed, never store plaintext

    # Status and progress
    status = Column(String(50), nullable=False, default="pending")
    progress_percentage = Column(Integer, default=0)
    progress_message = Column(Text, default="")
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # File system paths
    output_dir = Column(String(500), nullable=True)

    # Metadata
    estimated_duration_minutes = Column(Float, nullable=True)
    actual_duration_minutes = Column(Float, nullable=True)


class LLMInteraction(Base):
    """Database model for storing raw LLM prompts and responses"""
    __tablename__ = "llm_interactions"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(255), index=True, nullable=False)

    # LLM interaction details
    llm_model = Column(String(255), nullable=False)
    stage = Column(String(100), nullable=False)  # e.g., "wbs_level1", "cost_estimation"

    # Request data
    prompt_text = Column(Text, nullable=False)
    prompt_metadata = Column(JSON, nullable=True)  # Additional prompt context

    # Response data
    response_text = Column(Text, nullable=True)
    response_metadata = Column(JSON, nullable=True)  # Token counts, timing, etc.

    # Status and timing
    status = Column(String(50), nullable=False, default="pending")  # pending, completed, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Token usage (for cost tracking)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

    # Error information
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)


class PlanFile(Base):
    """Database model for tracking generated plan files"""
    __tablename__ = "plan_files"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(255), index=True, nullable=False)

    # File information
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # e.g., "report", "json", "csv"
    file_size_bytes = Column(Integer, nullable=True)

    # Content metadata
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash
    content_summary = Column(Text, nullable=True)  # Brief description of content

    # Generation information
    generated_by_stage = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # File system path
    file_path = Column(String(500), nullable=False)


class PlanMetrics(Base):
    """Database model for storing plan generation metrics and analytics"""
    __tablename__ = "plan_metrics"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(255), index=True, nullable=False)

    # Performance metrics
    total_llm_calls = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)

    # Quality metrics
    plan_complexity_score = Column(Float, nullable=True)
    plan_completeness_score = Column(Float, nullable=True)

    # User feedback (if implemented)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    user_feedback = Column(Text, nullable=True)

    # System metrics
    peak_memory_mb = Column(Float, nullable=True)
    cpu_time_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class PlanContent(Base):
    """Database model for storing actual plan file contents (Option 1 implementation)"""
    __tablename__ = "plan_content"
    __table_args__ = (
        # Composite index for fast filename lookups within a plan
        # This is critical for performance when Luigi tasks query existing content
        Index('idx_plan_content_plan_id_filename', 'plan_id', 'filename'),
        # Stage-based filtering index (useful for debugging specific pipeline stages)
        Index('idx_plan_content_stage', 'stage'),
    )

    id = Column(Integer, primary_key=True, index=True)
    # plan_id index defined via __table_args__ composite indexes
    plan_id = Column(String(255), nullable=False)

    # File identification
    filename = Column(String(255), nullable=False)  # e.g., "018-wbs_level1.json"
    stage = Column(String(100), nullable=True, index=True)  # e.g., "wbs_level1"
    content_type = Column(String(50), nullable=False)  # json, markdown, html, csv, txt

    # Actual content (stored in database for persistence)
    content = Column(Text, nullable=False)  # The actual file content
    content_size_bytes = Column(Integer, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)


# Database service functions
class DatabaseService:
    """Service class for database operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_plan(self, plan_data: dict) -> Plan:
        """Create a new plan record"""
        plan = Plan(**plan_data)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get plan by ID"""
        return self.db.query(Plan).filter(Plan.plan_id == plan_id).first()

    def update_plan(self, plan_id: str, update_data: dict) -> Optional[Plan]:
        """Update plan data"""
        plan = self.get_plan(plan_id)
        if plan:
            for key, value in update_data.items():
                setattr(plan, key, value)
            self.db.commit()
            self.db.refresh(plan)
        return plan

    def list_plans(self, user_id: Optional[str] = None, limit: int = 100) -> List[Plan]:
        """List plans, optionally filtered by user"""
        query = self.db.query(Plan)
        if user_id:
            query = query.filter(Plan.user_id == user_id)
        return query.order_by(Plan.created_at.desc()).limit(limit).all()

    def create_llm_interaction(self, interaction_data: dict) -> LLMInteraction:
        """Create a new LLM interaction record"""
        interaction = LLMInteraction(**interaction_data)
        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)
        return interaction

    def update_llm_interaction(self, interaction_id: int, update_data: dict) -> Optional[LLMInteraction]:
        """Update LLM interaction with response data"""
        interaction = self.db.query(LLMInteraction).filter(LLMInteraction.id == interaction_id).first()
        if interaction:
            for key, value in update_data.items():
                setattr(interaction, key, value)
            self.db.commit()
            self.db.refresh(interaction)
        return interaction

    def get_plan_interactions(self, plan_id: str) -> List[LLMInteraction]:
        """Get all LLM interactions for a plan"""
        return self.db.query(LLMInteraction).filter(LLMInteraction.plan_id == plan_id).all()

    def create_plan_file(self, file_data: dict) -> PlanFile:
        """Create a plan file record"""
        plan_file = PlanFile(**file_data)
        self.db.add(plan_file)
        self.db.commit()
        self.db.refresh(plan_file)
        return plan_file

    def get_plan_files(self, plan_id: str) -> List[PlanFile]:
        """Get all files for a plan"""
        return self.db.query(PlanFile).filter(PlanFile.plan_id == plan_id).all()

    def create_plan_metrics(self, metrics_data: dict) -> PlanMetrics:
        """Create plan metrics record"""
        metrics = PlanMetrics(**metrics_data)
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        return metrics

    def get_plan_metrics(self, plan_id: str) -> Optional[PlanMetrics]:
        """Get metrics for a plan"""
        return self.db.query(PlanMetrics).filter(PlanMetrics.plan_id == plan_id).first()

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a plan and all associated records"""
        plan = self.get_plan(plan_id)
        if plan:
            # Delete associated records
            self.db.query(LLMInteraction).filter(LLMInteraction.plan_id == plan_id).delete()
            self.db.query(PlanFile).filter(PlanFile.plan_id == plan_id).delete()
            self.db.query(PlanMetrics).filter(PlanMetrics.plan_id == plan_id).delete()
            self.db.query(PlanContent).filter(PlanContent.plan_id == plan_id).delete()
            
            # Delete the plan itself
            self.db.delete(plan)
            self.db.commit()
            return True
        return False

    def create_plan_content(self, content_data: dict) -> PlanContent:
        """Create plan content record (Option 3: persist file contents to DB)"""
        plan_content = PlanContent(**content_data)
        self.db.add(plan_content)
        self.db.commit()
        self.db.refresh(plan_content)
        return plan_content

    def get_plan_content(self, plan_id: str, filename: Optional[str] = None) -> List[PlanContent]:
        """Get plan content records, optionally filtered by filename"""
        query = self.db.query(PlanContent).filter(PlanContent.plan_id == plan_id)
        if filename:
            query = query.filter(PlanContent.filename == filename)
        return query.order_by(PlanContent.filename).all()

    def get_plan_content_by_filename(self, plan_id: str, filename: str) -> Optional[PlanContent]:
        """Get specific plan content by filename"""
        return self.db.query(PlanContent).filter(
            PlanContent.plan_id == plan_id,
            PlanContent.filename == filename
        ).first()

    def close(self):
        """Close database session"""
        self.db.close()


# Database connection management
def get_database():
    """Get DatabaseService instance for dependency injection"""
    db = SessionLocal()
    try:
        service = DatabaseService(db)
        yield service
    finally:
        db.close()


def get_database_service() -> DatabaseService:
    """Get DatabaseService instance directly (no generator)"""
    db = SessionLocal()
    return DatabaseService(db)


def get_raw_database():
    """Get raw database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session for dependency injection"""
    return SessionLocal()