"""
Author: Claude Code (claude-opus-4-1-20250805)
Date: 2025-09-19
PURPOSE: Pydantic models for API request/response schemas - ensures type safety and validation
SRP and DRY check: Pass - Single responsibility of data validation, DRY approach to schema definitions
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class PlanStatus(str, Enum):
    """Status of a plan generation job"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class SpeedVsDetail(str, Enum):
    """Speed vs detail trade-off options"""
    fast_basic = "FAST_BUT_BASIC"
    balanced = "BALANCED_SPEED_AND_DETAIL"
    detailed_slow = "ALL_DETAILS_BUT_SLOW"


class CreatePlanRequest(BaseModel):
    """Request to create a new plan"""
    prompt: str = Field(..., description="The planning prompt/idea", min_length=1, max_length=10000)
    llm_model: Optional[str] = Field(None, description="LLM model ID to use")
    speed_vs_detail: SpeedVsDetail = Field(SpeedVsDetail.detailed_slow, description="Speed vs detail preference")
    openrouter_api_key: Optional[str] = Field(None, description="OpenRouter API key for paid models")


class PlanResponse(BaseModel):
    """Response when creating or retrieving a plan"""
    plan_id: str = Field(..., description="Unique plan identifier")
    status: PlanStatus = Field(..., description="Current status of the plan")
    created_at: datetime = Field(..., description="When the plan was created")
    prompt: str = Field(..., description="The original planning prompt")
    progress_percentage: int = Field(0, description="Completion percentage (0-100)")
    progress_message: str = Field("", description="Current progress description")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    output_dir: Optional[str] = Field(None, description="Path to output directory")


class PlanProgressEvent(BaseModel):
    """Server-sent event for plan progress updates"""
    plan_id: str
    status: PlanStatus
    progress_percentage: int
    progress_message: str
    timestamp: datetime
    error_message: Optional[str] = None


class LLMModel(BaseModel):
    """Available LLM model information"""
    id: str = Field(..., description="Model identifier")
    label: str = Field(..., description="Human-readable model name")
    comment: str = Field(..., description="Model description/capabilities")
    priority: int = Field(0, description="Priority/ordering (lower = higher priority)")
    requires_api_key: bool = Field(False, description="Whether this model requires an API key")


class PromptExample(BaseModel):
    """Example prompt from the catalog"""
    uuid: str = Field(..., description="Unique prompt identifier")
    prompt: str = Field(..., description="The example prompt text")
    title: Optional[str] = Field(None, description="Short prompt title")


class PlanFilesResponse(BaseModel):
    """Response listing files in a completed plan"""
    plan_id: str
    files: List[str] = Field(..., description="List of generated filenames")
    has_report: bool = Field(..., description="Whether HTML report is available")


class APIError(BaseModel):
    """Standard API error response"""
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    """API health check response"""
    status: str = Field("healthy", description="API status")
    version: str = Field(..., description="API version")
    planexe_version: str = Field(..., description="PlanExe version")
    available_models: int = Field(..., description="Number of available LLM models")