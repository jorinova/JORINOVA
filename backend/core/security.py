"""JWT authentication + password hashing."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db

settings = get_settings()
oauth2   = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/token')

# Use bcrypt directly — avoids passlib/bcrypt 5.x compatibility issues
try:
    import bcrypt as _bcrypt
    def hash_password(plain: str) -> str:
        return _bcrypt.hashpw(plain.encode('utf-8'), _bcrypt.gensalt(rounds=12)).decode('utf-8')
    def verify_password(plain: str, hashed: str) -> bool:
        try:
            return _bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
except ImportError:
    # Fallback to passlib if bcrypt direct import fails
    from passlib.context import CryptContext
    _ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
    def hash_password(plain: str) -> str:  # type: ignore[misc]
        return _ctx.hash(plain)
    def verify_password(plain: str, hashed: str) -> bool:  # type: ignore[misc]
        return _ctx.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire  = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire))
    payload.update({'exp': expire, 'iat': datetime.now(timezone.utc)})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)):
    from models.user import User
    payload = decode_token(token)
    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(status_code=401, detail='Invalid token payload')
    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail='User not found or inactive')
    return user


def require_roles(*roles: str):
    def checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail=f'Role {current_user.role} not permitted')
        return current_user
    return checker
