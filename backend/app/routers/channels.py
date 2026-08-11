from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Channel
from app.schemas import ChannelOut, ChannelCreate, ChannelUpdate

router = APIRouter(prefix="/api/channels", tags=["channels"])

@router.get("", response_model=List[ChannelOut])
def list_channels(db: Session = Depends(get_db)):
    return db.query(Channel).order_by(Channel.id.asc()).all()

@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
    return ch

@router.put("/{channel_id}/status", response_model=ChannelOut)
def update_channel_status(channel_id: int, status_update: dict, db: Session = Depends(get_db)):
    ch = db.query(Channel).filter(Channel.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="채널을 찾을 수 없습니다.")
    
    new_status = status_update.get("status")
    if new_status not in ["on", "off"]:
        raise HTTPException(status_code=400, detail="수집상태는 'on' 또는 'off' 만 가능합니다.")
    
    ch.status = new_status
    db.commit()
    db.refresh(ch)
    return ch

@router.post("", response_model=ChannelOut)
def create_channel(ch_in: ChannelCreate, db: Session = Depends(get_db)):
    existing = db.query(Channel).filter(Channel.identifier == ch_in.identifier).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 채널 식별자입니다.")
    
    ch = Channel(
        name=ch_in.name,
        identifier=ch_in.identifier,
        handle=ch_in.handle,
        url=ch_in.url,
        status=ch_in.status
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch
