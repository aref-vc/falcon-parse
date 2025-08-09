from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid
from datetime import datetime

class ScrapeStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapeRequest(BaseModel):
    url: HttpUrl
    data_type: str
    custom_instructions: Optional[str] = None
    
class ScrapeJob(BaseModel):
    job_id: str
    url: str
    data_type: str
    custom_instructions: Optional[str] = None
    status: ScrapeStatus = ScrapeStatus.PENDING
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
class ScrapeResult(BaseModel):
    job_id: str
    status: ScrapeStatus
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: Optional[int] = None
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    
class JobStatus(BaseModel):
    job_id: str
    status: ScrapeStatus
    progress: Optional[int] = None
    message: Optional[str] = None
    
class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    gemini_api: bool