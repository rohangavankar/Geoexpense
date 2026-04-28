from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Company, User, InviteToken
from auth import generate_invite_token
from deps import get_current_user, require_admin

router = APIRouter(prefix="/api/company", tags=["company"])


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
