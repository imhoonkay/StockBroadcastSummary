from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from app.config import settings
from app.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    if req.username == "admin" and req.password == "passw0rd!":
        access_token = create_access_token(data={"sub": req.username})
        return TokenResponse(access_token=access_token, username=req.username)
    
    if req.username and req.password:
        access_token = create_access_token(data={"sub": req.username})
        return TokenResponse(access_token=access_token, username=req.username)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
