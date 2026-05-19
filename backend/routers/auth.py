"""Authentication router — login, token, profile, password reset, forgot password OTP."""
import random
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from core.database import get_db
from core.security import (hash_password, verify_password,
                            create_access_token, get_current_user)
from models.user import User, LoginLog

# In-memory OTP store: {email: (otp, expires_at)}
_otp_store: dict = {}

router = APIRouter(prefix='/auth', tags=['Authentication'])


class TokenOut(BaseModel):
    access_token: str
    token_type:   str = 'bearer'
    user_id:      int
    username:     str
    role:         str
    full_name:    str


class UserOut(BaseModel):
    id:               int
    username:         str
    email:            str
    first_name:       str
    last_name:        str
    role:             str
    department:       str | None = None
    is_active:        bool
    photo_url:        str | None = None   # profile photo for header sphere
    has_2fa:          bool       = False
    preferred_language: str      = 'en'
    model_config = {'from_attributes': True}


class UserOutFull(UserOut):
    """Extended user info returned from /me after login."""
    full_name:     str = ''
    is_superuser:  bool = False
    hospital_id:   int | None = None
    employee_id:   str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password:     str


class CreateUserIn(BaseModel):
    username:   str
    email:      str
    password:   str
    first_name: str = ''
    last_name:  str = ''
    role:       str = 'lab_technician'
    department: str | None = None


@router.post('/token', response_model=TokenOut)
async def login(
    form:    OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db:      Session = Depends(get_db),
):
    user = db.query(User).filter(
        (User.username == form.username) | (User.email == form.username)
    ).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account inactive')

    token = create_access_token({'sub': str(user.id), 'role': user.role})

    db.add(LoginLog(
        user_id=user.id, success=True, method='password',
        ip_address=request.client.host if request else None,
    ))
    db.commit()
    return TokenOut(
        access_token=token, user_id=user.id, username=user.username,
        role=user.role, full_name=user.full_name,
    )


@router.get('/me')
def me(current_user: User = Depends(get_current_user)):
    """Return full user profile including photo URL for header sphere."""
    return {
        'id':          current_user.id,
        'username':    current_user.username,
        'email':       current_user.email,
        'first_name':  current_user.first_name,
        'last_name':   current_user.last_name,
        'full_name':   current_user.full_name,
        'role':        current_user.role,
        'department':  getattr(current_user, 'department', None),
        'is_active':   current_user.is_active,
        'is_superuser':current_user.is_superuser,
        'photo_url':   getattr(current_user, 'profile_photo', None),
        'has_2fa':     getattr(current_user, 'two_factor_enabled', False),
        'preferred_language': getattr(current_user, 'preferred_language', 'en'),
        'hospital_id': getattr(current_user, 'hospital_id', None),
        'employee_id': getattr(current_user, 'employee_id', None),
    }


@router.post('/change-password')
def change_password(
    body:         PasswordChange,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail='Current password incorrect')
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {'message': 'Password changed successfully'}


@router.post('/create-user', response_model=UserOut)
def create_user(
    body:         CreateUserIn,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    if current_user.role not in ('super_admin', 'it_admin'):
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail='Username already exists')
    user = User(
        username=body.username, email=body.email,
        hashed_password=hash_password(body.password),
        first_name=body.first_name, last_name=body.last_name,
        role=body.role, department=body.department,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Forgot Password / OTP Reset ───────────────────────────────────────────────

class ForgotPasswordIn(BaseModel):
    email: str


class VerifyOTPIn(BaseModel):
    email:    str
    otp:      str
    new_password: str


def _generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


def _send_otp_email(email: str, otp: str, username: str) -> bool:
    """
    Send OTP via email. In production: configure SMTP in .env.
    Logs the OTP to server console as fallback (dev mode).
    """
    import logging
    log = logging.getLogger('auth.otp')
    log.info('='*50)
    log.info(f'OTP RESET for {username} <{email}>: {otp}')
    log.info(f'Expires in 15 minutes.')
    log.info('='*50)

    try:
        import smtplib, os
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_host = os.environ.get('EMAIL_HOST', '')
        smtp_user = os.environ.get('EMAIL_HOST_USER', '')
        smtp_pass = os.environ.get('EMAIL_HOST_PASSWORD', '')
        smtp_port = int(os.environ.get('EMAIL_PORT', 587))

        if not smtp_host or not smtp_user:
            return True   # dev mode — OTP logged to console

        msg = MIMEMultipart()
        msg['From']    = f'JORINOVA NEXUS ALIS-X <{smtp_user}>'
        msg['To']      = email
        msg['Subject'] = 'ALIS-X Password Reset OTP'
        body = f"""
Hello {username},

Your password reset OTP is:

    {otp}

This code expires in 15 minutes.
If you did not request a password reset, please ignore this email.

JORINOVA NEXUS ALIS-X Security System
        """.strip()
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, email, msg.as_string())
        return True
    except Exception as e:
        log.warning(f'Email send failed (OTP still valid — check console): {e}')
        return True   # OTP still valid even if email fails


@router.post('/forgot-password')
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)):
    """
    Step 1: Request OTP. Sends a 6-digit code to the registered email.
    Always returns 200 (to avoid user enumeration attacks).
    """
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        otp     = _generate_otp()
        expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        _otp_store[body.email.lower()] = (otp, expires)
        _send_otp_email(user.email, otp, user.username)
    return {'message': 'If that email is registered, an OTP has been sent.'}


@router.post('/verify-otp-reset')
def verify_otp_reset(body: VerifyOTPIn, db: Session = Depends(get_db)):
    """
    Step 2: Verify OTP and set new password.
    """
    key    = body.email.lower()
    stored = _otp_store.get(key)

    if not stored:
        raise HTTPException(status_code=400, detail='No OTP requested for this email')

    otp, expires = stored
    if datetime.now(timezone.utc) > expires:
        _otp_store.pop(key, None)
        raise HTTPException(status_code=400, detail='OTP has expired. Request a new one.')

    if otp != body.otp.strip():
        raise HTTPException(status_code=400, detail='Invalid OTP')

    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail='Password must be at least 8 characters')

    user.hashed_password = hash_password(body.new_password)
    db.commit()
    _otp_store.pop(key, None)   # invalidate OTP after use

    import logging
    logging.getLogger('auth.otp').info(f'Password reset successful for {user.username}')
    return {'message': 'Password reset successful. Please log in with your new password.'}
