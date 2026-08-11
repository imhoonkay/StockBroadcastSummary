from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models import SubtitleBuffer

router = APIRouter(prefix="/api/buffers", tags=["buffers"])

class SubtitleBufferOut(BaseModel):
    id: int
    channel_id: int
    channel_identifier: str
    window_label: str
    chunk_text: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[SubtitleBufferOut])
def list_subtitle_buffers(
    channel_identifier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(SubtitleBuffer)
    if channel_identifier:
        query = query.filter(SubtitleBuffer.channel_identifier == channel_identifier)
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(SubtitleBuffer.created_at >= s_dt)
        except Exception:
            pass
    if end_date:
        try:
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(SubtitleBuffer.created_at <= e_dt)
        except Exception:
            pass
    return query.order_by(SubtitleBuffer.id.desc()).all()

@router.get("/{buffer_id}", response_model=SubtitleBufferOut)
def get_subtitle_buffer(buffer_id: int, db: Session = Depends(get_db)):
    buf = db.query(SubtitleBuffer).filter(SubtitleBuffer.id == buffer_id).first()
    if not buf:
        raise HTTPException(status_code=404, detail="자막 버퍼 조각을 찾을 수 없습니다.")
    return buf
