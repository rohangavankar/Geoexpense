from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, Company, User, InviteToken
from auth import generate_invite_token, hash_password, verify_password
from deps import get_current_user, require_admin

router = APIRouter(prefix="/api/company", tags=["company"])


# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=8)


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "company_name": current_user.company.name if current_user.company else "",
    }


@router.put("/profile")
def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.name:
        current_user.name = body.name

    if body.new_password:
        if not body.current_password:
            raise HTTPException(400, "Current password is required to set a new password")
        if not current_user.hashed_password or not verify_password(body.current_password, current_user.hashed_password):
            raise HTTPException(400, "Current password is incorrect")
        current_user.hashed_password = hash_password(body.new_password)

    db.commit()
    db.refresh(current_user)
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "company_name": current_user.company.name if current_user.company else "",
    }


@router.get("/members")
def list_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    members = db.query(User).filter(
        User.company_id == current_user.company_id,
        User.is_active == True,
    ).all()
    return [
        {"id": m.id, "name": m.name, "email": m.email, "role": m.role}
        for m in members
    ]


class InviteBody(BaseModel):
    role: str = "member"


@router.post("/invite")
def create_invite(
    body: InviteBody,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    token = generate_invite_token()
    invite = InviteToken(
        token=token,
        company_id=current_user.company_id,
        role=body.role,
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_by=current_user.id,
    )
    db.add(invite)
    db.commit()
    return {"invite_token": token, "role": body.role}


class RoleBody(BaseModel):
    role: str


@router.patch("/members/{user_id}/role")
def update_role(
    user_id: int,
    body: RoleBody,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.role not in ("owner", "admin", "member"):
        raise HTTPException(400, "Invalid role")
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == current_user.company_id,
    ).first()
    if not user:
        raise HTTPException(404, "Member not found")
    if user.id == current_user.id:
        raise HTTPException(400, "Cannot change your own role")
    user.role = body.role
    db.commit()
    return {"ok": True}


@router.delete("/members/{user_id}")
def remove_member(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == current_user.company_id,
    ).first()
    if not user:
        raise HTTPException(404, "Member not found")
    if user.id == current_user.id:
        raise HTTPException(400, "Cannot remove yourself")
    user.is_active = False
    db.commit()
    return {"ok": True}
