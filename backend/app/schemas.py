from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ChannelBase(BaseModel):
    name: str
    identifier: str
    handle: str
    url: str
    status: str

class ChannelCreate(ChannelBase):
    pass

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    handle: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None

class ChannelOut(ChannelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SubtitleFileOut(BaseModel):
    id: int
    channel_id: int
    channel_identifier: str
    file_name: str
    file_path: str
    file_size: int
    window_label: str
    transcript_text: str
    collected_at: datetime

    class Config:
        from_attributes = True

class SummaryOut(BaseModel):
    id: int
    channel_id: int
    subtitle_file_id: Optional[int] = None
    channel_identifier: str
    window_label: str
    summary_text: str
    created_at: datetime

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
