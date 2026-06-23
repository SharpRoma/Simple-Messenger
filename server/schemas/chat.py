from pydantic import BaseModel
from typing import List, Optional

class ChatResponse(BaseModel):
    id: int
    name: str
    type: str
    encrypted_key: Optional[str] = None

class ChatListResponse(BaseModel):
    chats: List[ChatResponse]

class CreateDialogRequest(BaseModel):
    target_username: str

class CreateGroupRequest(BaseModel):
    name: str

class AddMemberRequest(BaseModel):
    username: str

class CreateSecretChatRequest(BaseModel):
    target_username: str
    encrypted_key_sender: str
    encrypted_key_recipient: str