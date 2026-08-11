from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Summary
from app.schemas import SummaryOut

router = APIRouter(prefix="/api/summaries", tags=["summaries"])

from datetime import datetime

@router.get("", response_model=List[SummaryOut])
def list_summaries(
    channel_id: Optional[int] = None,
    channel_identifier: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Summary)
    if channel_id:
        query = query.filter(Summary.channel_id == channel_id)
    if channel_identifier:
        query = query.filter(Summary.channel_identifier == channel_identifier)
    if start_date:
        try:
            s_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Summary.created_at >= s_dt)
        except Exception:
            pass
    if end_date:
        try:
            e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Summary.created_at <= e_dt)
        except Exception:
            pass
    return query.order_by(Summary.created_at.desc()).all()

@router.get("/{summary_id}", response_model=SummaryOut)
def get_summary(summary_id: int, db: Session = Depends(get_db)):
    summary = db.query(Summary).filter(Summary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="요약 데이터를 찾을 수 없습니다.")
    return summary
