from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import SubtitleFile
from app.schemas import SubtitleFileOut

router = APIRouter(prefix="/api/subtitles", tags=["subtitles"])

from datetime import datetime

@router.get("", response_model=List[SubtitleFileOut])
def list_subtitle_files(
    channel_id: Optional[int] = None,
    channel_identifier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(SubtitleFile)
    if channel_id:
        query = query.filter(SubtitleFile.channel_id == channel_id)
    if channel_identifier:
        query = query.filter(SubtitleFile.channel_identifier == channel_identifier)
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(SubtitleFile.collected_at >= s_dt)
        except Exception:
            pass
    if end_date:
        try:
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(SubtitleFile.collected_at <= e_dt)
        except Exception:
            pass
    return query.order_by(SubtitleFile.collected_at.desc()).all()

@router.get("/{subtitle_id}", response_model=SubtitleFileOut)
def get_subtitle_file(subtitle_id: int, db: Session = Depends(get_db)):
    sub = db.query(SubtitleFile).filter(SubtitleFile.id == subtitle_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="자막 파일을 찾을 수 없습니다.")
    return sub
