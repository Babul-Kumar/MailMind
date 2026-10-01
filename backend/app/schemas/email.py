from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class TopSignal(BaseModel):
    term: str
    weight: float


class ClassifiedEmail(BaseModel):
    email_id: str
    date: str
    sender: str
    recipients: Optional[str] = ""
    subject: str
    body: Optional[str] = ""
    snippet: Optional[str] = ""
    predicted_priority: str
    priority_name: str
    model_priority: Optional[str] = None
    final_priority: Optional[str] = None
    action_required: bool = False
    action_reason: Optional[str] = None
    topic: str = "other"
    deadline_detected: bool = False
    deadline_datetime: Optional[str] = None
    deadline_precision: str = "NONE"
    deadline_display: Optional[str] = None
    refinement_applied: bool = False
    refinement_reason: Optional[str] = None
    refinement_signals: List[str] = []
    review_suggested: bool = False
    confidence: float
    confidence_level: str
    probabilities: Dict[str, float]
    explanation: str
    top_signals: List[TopSignal] = []


class PriorityCounts(BaseModel):
    P1: int = 0
    P2: int = 0
    P3: int = 0
    P4: int = 0


class PriorityPercentages(BaseModel):
    P1: float = 0.0
    P2: float = 0.0
    P3: float = 0.0
    P4: float = 0.0


class InboxStats(BaseModel):
    total_analyzed: int
    refined_count: int = 0
    refinement_rate: float = 0.0
    counts: PriorityCounts
    percentages: PriorityPercentages
    average_confidence: float
    highest_priority_count: int
    last_synced: str
    query_applied: str


class ProfileInfo(BaseModel):
    email_address: str
    messages_total: int
    threads_total: int


class EmailsResponse(BaseModel):
    status: str
    profile: ProfileInfo
    stats: InboxStats
    emails: List[ClassifiedEmail]
