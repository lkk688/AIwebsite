from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core import security
from app.core.config import settings
from app.adapters import db
from app.api import deps
from pydantic import BaseModel

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    is_active: bool = True
    is_superuser: bool = False

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/login/access-token", response_model=Token)
async def login_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = db.get_user_by_username(form_data.username)
    if not user or not security.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = security.create_access_token(
        subject=user["username"], expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@router.post("/update-password")
async def update_password(
    request: PasswordChangeRequest,
    current_user: Annotated[dict, Depends(deps.get_current_active_superuser)]
):
    """
    Update the current user's password.
    """
    # Verify old password
    if not security.verify_password(request.old_password, current_user["hashed_password"]):
        raise HTTPException(
            status_code=400,
            detail="Incorrect old password"
        )
    
    # Hash new password
    hashed_password = security.get_password_hash(request.new_password)
    
    # Update in DB
    success = db.update_user_password(current_user["username"], hashed_password)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to update password"
        )
    
    return {"status": "success", "message": "Password updated successfully"}

@router.post("/test-token", response_model=User)
async def test_token(current_user: Annotated[dict, Depends(security.get_password_hash)]): 
    # This is just a placeholder, real dependency needed in main or common
    return current_user
