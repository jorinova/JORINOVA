"""
First-run setup wizard endpoints.

Lets a brand-new deployment be brought up without manually editing seed
scripts: the front-end /install page calls these to discover whether
setup is needed, then to create the first hospital + admin + default
language in one transaction.

Endpoints (all unauthenticated by design — the system has no users yet
when these are called):

  GET  /api/v1/setup/status   - {needs_setup: bool, has_hospital, has_admin}
  POST /api/v1/setup/init     - create hospital + admin + system language
                                Returns 409 if setup was already done, so it
                                cannot be used to overwrite an existing
                                install.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import hash_password
from models.user import User
from models.core_config import Hospital

router = APIRouter(prefix='/setup', tags=['Setup'])
log = logging.getLogger('alis_x.setup')


# ── Schemas ───────────────────────────────────────────────────────────────────

class SetupStatus(BaseModel):
    needs_setup:  bool
    has_hospital: bool
    has_admin:    bool


class SetupInit(BaseModel):
    # Language chosen by the installing admin — used as the default for
    # every new user created in the system.
    language:        Literal['en', 'fr', 'rw'] = 'en'
    # Hospital identity
    hospital_name:   str           = Field(..., min_length=2, max_length=200)
    hospital_district: str | None  = Field(None, max_length=80)
    hospital_province: str | None  = Field(None, max_length=80)
    hospital_phone:    str | None  = Field(None, max_length=30)
    hospital_email:    EmailStr | None = None
    # Admin account
    admin_username:  str           = Field(..., min_length=3, max_length=30)
    admin_first_name:str           = Field(..., min_length=1, max_length=80)
    admin_last_name: str           = Field(..., min_length=1, max_length=80)
    admin_email:     EmailStr
    admin_password:  str           = Field(..., min_length=8, max_length=200)


class SetupResult(BaseModel):
    message:       str
    hospital_id:   int
    admin_user_id: int
    language:      str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get('/status', response_model=SetupStatus)
def status_(db: Session = Depends(get_db)):
    has_hospital = db.query(Hospital).count() > 0
    has_admin    = db.query(User).filter(User.is_superuser.is_(True)).count() > 0
    return SetupStatus(
        needs_setup  = not (has_hospital and has_admin),
        has_hospital = has_hospital,
        has_admin    = has_admin,
    )


@router.post('/init', response_model=SetupResult, status_code=status.HTTP_201_CREATED)
def init(body: SetupInit, db: Session = Depends(get_db)):
    """Idempotency: refuses to run if a hospital or admin already exists.
    This way the public endpoint can't be used to silently take over an
    existing install."""
    if db.query(Hospital).count() > 0 or db.query(User).filter(User.is_superuser.is_(True)).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='System is already initialised. Setup can only run once.',
        )

    hospital = Hospital(
        name      = body.hospital_name.strip(),
        district  = (body.hospital_district or '').strip() or None,
        province  = (body.hospital_province or '').strip() or None,
        phone     = (body.hospital_phone or '').strip() or None,
        email     = (body.hospital_email or None),
        is_active = True,
    )
    db.add(hospital)
    db.flush()                                                  # so we have hospital.id

    admin = User(
        username           = body.admin_username.strip().lower(),
        email              = body.admin_email,
        first_name         = body.admin_first_name.strip(),
        last_name          = body.admin_last_name.strip(),
        hashed_password    = hash_password(body.admin_password),
        role               = 'super_admin',
        is_active          = True,
        is_superuser       = True,
        preferred_language = body.language,
        hospital_id        = hospital.id,
    )
    db.add(admin)
    db.commit()

    log.info(
        'Initial setup completed: hospital=%s admin=%s lang=%s',
        hospital.name, admin.username, body.language,
    )
    return SetupResult(
        message       = 'Setup complete. You can now sign in.',
        hospital_id   = hospital.id,
        admin_user_id = admin.id,
        language      = body.language,
    )
