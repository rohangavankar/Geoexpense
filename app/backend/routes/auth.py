import os
import re
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db, User, Company, InviteToken
from auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, generate_invite_token,
)
from deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8000")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "company"


def _unique_slug(db: Session, base: str) -> str:
    slug, n = base, 1
    while db.query(Company).filter(Company.slug == slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


# ── Models ────────────────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    name: str
    email: str
    password: str
    company_name: str
    invite_token: str | None = None


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.company_id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
            "company_name": user.company.name if user.company else "",
        },
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/invite/{token}")
def get_invite(token: str, db: Session = Depends(get_db)):
    invite = db.query(InviteToken).filter(
        InviteToken.token == token,
        InviteToken.used == False,
    ).first()
    if not invite:
        raise HTTPException(404, "Invalid or expired invite link")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invite link has expired")
    company = db.query(Company).filter(Company.id == invite.company_id).first()
    return {"company_name": company.name if company else "Unknown", "role": invite.role}


@router.post("/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "Email already registered")

    # Joining via invite token
    if body.invite_token:
        invite = db.query(InviteToken).filter(
            InviteToken.token == body.invite_token,
            InviteToken.used == False,
        ).first()
        if not invite:
            raise HTTPException(400, "Invalid or expired invite link")
        if invite.expires_at and invite.expires_at < datetime.utcnow():
            raise HTTPException(400, "Invite link has expired")
        company = db.query(Company).filter(Company.id == invite.company_id).first()
        role = invite.role
        invite.used = True
    else:
        slug = _unique_slug(db, _slugify(body.company_name))
        company = Company(name=body.company_name, slug=slug)
        db.add(company)
        db.flush()
        role = "owner"

    user = User(
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
        company_id=company.id,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.is_active == True).first()
    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    return _token_response(user)


@router.post("/refresh")
def refresh(body: RefreshBody, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise HTTPException(401, "User not found")
    return _token_response(user)


@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.refresh(current_user)
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "company_id": current_user.company_id,
        "company_name": current_user.company.name if current_user.company else "",
    }


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google")
def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth not configured — set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
def google_callback(code: str, db: Session = Depends(get_db)):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth not configured")

    # Exchange code for tokens
    token_res = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    if token_res.status_code != 200:
        raise HTTPException(400, "Failed to exchange Google code")

    id_token = token_res.json().get("id_token")
    userinfo_res = httpx.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {token_res.json()['access_token']}"},
    )
    info = userinfo_res.json()
    google_id = info.get("sub")
    email = info.get("email")
    name = info.get("name", email.split("@")[0])

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
        else:
            domain = email.split("@")[1].split(".")[0]
            slug = _unique_slug(db, _slugify(domain))
            company = Company(name=domain.capitalize(), slug=slug)
            db.add(company)
            db.flush()
            user = User(email=email, name=name, google_id=google_id, company_id=company.id, role="owner")
            db.add(user)
    db.commit()
    db.refresh(user)

    tokens = _token_response(user)
    redirect = (
        f"{FRONTEND_URL}/auth-callback.html"
        f"?access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
    )
    return RedirectResponse(redirect)
