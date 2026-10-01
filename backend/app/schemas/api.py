from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    model_loaded: bool
    timestamp: str


class ModelInfoResponse(BaseModel):
    status: str
    model_name: str
    model_state: str
    vocabulary_features: int
    classes: List[str]
    priority_mapping: Dict[str, str]
    verification_status: str


class GmailProfileResponse(BaseModel):
    status: str
    email_address: str
    messages_total: int
    threads_total: int
    access_scope: str
