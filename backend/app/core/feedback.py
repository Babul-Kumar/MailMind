import os
import json
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.core.config import BASE_DIR

FEEDBACK_DIR = os.path.join(BASE_DIR, "dataset", "feedback")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback.jsonl")


class FeedbackSubmission(BaseModel):
    message_id: str
    model_version: str
    predicted_priority: str
    corrected_priority: Optional[str] = None
    predicted_action_required: bool
    corrected_action_required: Optional[bool] = None
    deadline_correction: Optional[bool] = None
    corrected_deadline_display: Optional[str] = None
    topic_correction: Optional[str] = None
    notes: Optional[str] = None


class FeedbackManager:
    """
    Stores human correction and reviewed user feedback separately from live inference state.
    Feedback accumulates for future reviewed dataset version creation (e.g. dataset-v3).
    """
    def __init__(self):
        os.makedirs(FEEDBACK_DIR, exist_ok=True)

    def record_feedback(
        self,
        submission: Optional[FeedbackSubmission] = None,
        user_id: str = "default_user",
        **kwargs
    ) -> Dict[str, Any]:
        data = submission.dict() if submission is not None else kwargs
        record = {
            **data,
            "user_id": user_id,
            "feedback_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "pending_review"
        }
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def list_feedback(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not os.path.exists(FEEDBACK_FILE):
            return []
        records = []
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        return records[-limit:]


feedback_manager = FeedbackManager()
