from pydantic import BaseModel
from typing import List

class ChatResponse(BaseModel):
    id: int
    name: str
    type: str

class ChatListResponse(BaseModel):
    chats: List[ChatResponse]

class CreateDialogRequest(BaseModel):
    target_username: str