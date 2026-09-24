from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

class TaskStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class ProcessingTask:
    id: str 
    user_id: int
    image_s3_key: str
    task_type: str  # '2D' or '3D'
    status: str = TaskStatus.PENDING
    result_data: Optional[Dict] = None
    error_log: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def mark_failed(self, error_message: str):
        self.status = TaskStatus.FAILED
        self.error_log = error_message

    def mark_completed(self, result: Dict):
        self.status = TaskStatus.COMPLETED
        self.result_data = result
