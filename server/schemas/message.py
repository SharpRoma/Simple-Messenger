from pydantic import BaseModel
from typing import List, Optional

class MessageResponse(BaseModel):
    id: int
    sender: str
    text: Optional[str] = None
    file_name: Optional[str] = None
    timestamp: int

class HistoryResponse(BaseModel):
    chat_id: int
    messages: List[MessageResponse]