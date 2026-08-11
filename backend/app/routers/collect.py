from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.scheduler_service import collect_and_summarize_all

router = APIRouter(prefix="/api/collect", tags=["collect"])

@router.post("/run")
async def trigger_manual_collection(
    channel_id: int = None,
    db: Session = Depends(get_db)
):
    """Trigger subtitle collection & Gemini AI summary immediately"""
    results = await collect_and_summarize_all(db, channel_id=channel_id)
    return {
        "message": "수집 및 요약 작업이 실행되었습니다.",
        "results": results
    }
