from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db, User
from auth import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not credentials:
        raise exc
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise exc
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active == True).first()
    if not user:
        raise exc
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
