"""
JORINOVA NEXUS ALIS-X — SMS Notification Service
=================================================
Rwanda hospital SMS via Africa's Talking API (covers MTN + Airtel Rwanda).
Fallback: logs message if API key not configured.

SMS types:
  result_ready       — Patient notified when results are validated
  critical_value     — Clinician notified of critical result
  otp_2fa            — 2FA one-time password
  appointment_reminder — Patient appointment reminder
  low_stock          — Lab manager notified of low reagent stock
  shift_reminder     — Staff shift reminder

Templates are bilingual (English + Kinyarwanda).
All SMS messages are logged to sms_queue for audit.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger('sms_service')


# ── SMS Templates ─────────────────────────────────────────────────────────────

TEMPLATES = {

    'result_ready': {
        'en': (
            'NEXUS LAB: Dear {patient_name}, your lab results (Ref: {lid}) '
            'are ready. Collect at {hospital_name} or ask your doctor. '
            'Ref: {date}. ☎ {hospital_phone}'
        ),
        'rw': (
            'NEXUS LAB: Muramutse {patient_name}, ibisubizo bya lab (No: {lid}) '
            'birateguye. Baza i {hospital_name}. Tarehe: {date}. ☎ {hospital_phone}'
        ),
        'fr': (
            'NEXUS LAB: {patient_name}, vos résultats (Réf: {lid}) '
            'sont prêts. Récupérez-les à {hospital_name}. ☎ {hospital_phone}'
        ),
    },

    'critical_value': {
        'en': (
            '🚨 NEXUS LAB CRITICAL: Patient {patient_pid} — {test_name}: {value} {unit} '
            '[{flag}]. IMMEDIATE action required. '
            'Contact: {hospital_name} Lab ☎ {hospital_phone}'
        ),
    },

    'otp_2fa': {
        'en': (
            'NEXUS ALIS-X: Your 2FA code is {otp}. '
            'Valid for 30 seconds. Do not share this code.'
        ),
        'rw': (
            'NEXUS ALIS-X: Kode yawe ni {otp}. '
            'Ikora amasegonda 30. Ntutangaze uwo kode.'
        ),
    },

    'low_stock': {
        'en': (
            'NEXUS LAB ALERT: Low stock — {item_name} '
            '({remaining} {unit} remaining, reorder level: {reorder_level}). '
            'Action needed: {hospital_name} Lab Manager.'
        ),
    },

    'shift_reminder': {
        'en': (
            'NEXUS LAB: Reminder — your {shift_name} shift starts at {start_time} '
            'at {hospital_name}. Please confirm attendance.'
        ),
        'rw': (
            'NEXUS LAB: Gutuza — akazi kawe ka {shift_name} gatangira saa {start_time} '
            'i {hospital_name}.'
        ),
    },

    'enrollment_approved': {
        'en': (
            'NEXUS ALIS-X: Your voice biometric enrollment has been approved. '
            'Voice commands are now enabled on your account. — {hospital_name}'
        ),
    },

    'appointment_reminder': {
        'en': (
            'NEXUS LAB: Reminder — you have a lab appointment tomorrow at {time}. '
            'Bring your ID and insurance card. {hospital_name} ☎ {hospital_phone}'
        ),
        'rw': (
            'NEXUS LAB: Wibutse — ufite gahunda ya lab ejo saa {time}. '
            'Zana indangamuntu n\'icyangombwa cya ubuzima bwawe.'
        ),
    },
}


# ── Core sender ───────────────────────────────────────────────────────────────

async def send_sms(
    phone:    str,
    message:  str,
    sms_type: str = 'generic',
    patient_id: Optional[int] = None,
    patient_pid: Optional[str] = None,
    db=None,
) -> dict:
    """
    Send an SMS via Africa's Talking API.
    Falls back to logging if no API key configured.

    Returns: {'status': 'sent'|'queued'|'failed', 'message_id': str}
    """
    # Normalise to E.164 (supports all countries, defaults to Rwanda for bare numbers)
    phone = normalise_phone(phone)
    if not phone:
        log.error('Invalid phone number: %s', phone)
        return {'status': 'failed', 'error': 'Invalid phone number'}

    # Truncate message (160 chars per SMS)
    if len(message) > 160:
        message = message[:157] + '...'

    # Log to queue first (audit)
    await _queue_sms(db, phone, message, sms_type, patient_id, patient_pid)

    # Try to send
    at_username = os.environ.get('AT_USERNAME', '')
    at_api_key  = os.environ.get('AT_API_KEY',  '')

    if not at_username or not at_api_key:
        log.warning('Africa\'s Talking not configured — SMS queued only: %s → %s', phone, message[:60])
        return {
            'status':     'queued',
            'message_id': None,
            'note':       'SMS queued (AT_USERNAME/AT_API_KEY not set in .env.production)',
        }

    try:
        import africastalking
        africastalking.initialize(at_username, at_api_key)
        sms_client = africastalking.SMS

        result = await _send_via_at(sms_client, phone, message)
        log.info('SMS sent: %s → %s (id=%s)', phone, message[:40], result.get('messageId'))
        await _mark_sent(db, phone, result.get('messageId'))
        return {'status': 'sent', 'message_id': result.get('messageId'), 'cost': result.get('cost')}

    except ImportError:
        log.error('africastalking not installed. Run: pip install africastalking')
        return {'status': 'failed', 'error': 'africastalking not installed'}
    except Exception as e:
        log.error('SMS send error: %s', e)
        return {'status': 'failed', 'error': str(e)}


async def _send_via_at(sms_client, phone: str, message: str) -> dict:
    """Sync wrapper for Africa's Talking SMS (they use sync API)."""
    import asyncio
    loop = asyncio.get_event_loop()
    sender_id = os.environ.get('SMS_SENDER_ID', 'NEXUSLAB')
    return await loop.run_in_executor(
        None,
        lambda: sms_client.send(message, [phone], sender_id=sender_id)['SMSMessageData']['Recipients'][0]
    )


def normalise_phone(phone: str, default_country: str = 'RW') -> Optional[str]:
    """
    Normalise any phone number to E.164 format (+CCXXXXXXXXX).

    Uses Google's libphonenumber (via the `phonenumbers` package) which
    covers every ITU-allocated country code (240+ countries).

    Rules:
      - Numbers that already start with '+' are parsed as international.
      - Numbers without '+' are first tried as international (bare country
        code), then as local numbers in `default_country` (default: Rwanda).
      - Returns None for numbers that cannot be parsed or are invalid.

    Examples (default_country='RW'):
      '0788123456'       → '+250788123456'   (Rwanda local)
      '788123456'        → '+250788123456'   (Rwanda, no leading 0)
      '+250788123456'    → '+250788123456'   (already E.164)
      '+33612345678'     → '+33612345678'    (France)
      '+14155552671'     → '+14155552671'    (USA)
      '+254712345678'    → '+254712345678'   (Kenya)
      '+27821234567'     → '+27821234567'    (South Africa)
      'garbage'          → None
    """
    if not phone:
        return None
    phone = phone.strip()

    try:
        import phonenumbers
        from phonenumbers import NumberParseException, PhoneNumberFormat

        # Try parsing as-is (works if number has country code)
        try:
            parsed = phonenumbers.parse(phone, None)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        except NumberParseException:
            pass

        # Fallback: treat as local number in default_country
        try:
            parsed = phonenumbers.parse(phone, default_country)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        except NumberParseException:
            pass

        return None

    except ImportError:
        # phonenumbers not installed — Rwanda-only fallback
        log.warning('phonenumbers not installed; using Rwanda-only fallback normaliser')
        return _normalise_rwandan_fallback(phone)


def _normalise_rwandan_fallback(phone: str) -> Optional[str]:
    """Rwanda-only E.164 normaliser used when phonenumbers is not installed."""
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) == 10 and digits.startswith(('07', '08')):
        return '+250' + digits[1:]
    if len(digits) == 9 and digits[0] in ('7', '8'):
        return '+250' + digits
    if len(digits) == 12 and digits.startswith('250'):
        return '+' + digits
    if phone.startswith('+') and len(phone) >= 10:
        return phone
    return None


# Keep old name as alias for backward compatibility
_normalise_rwandan_phone = normalise_phone


async def _queue_sms(db, phone, message, sms_type, patient_id, patient_pid):
    """Write SMS to queue table for audit."""
    if not db:
        return
    try:
        from models.notifications import SMSQueue
        q = SMSQueue(
            phone_number=phone, message=message, sms_type=sms_type,
            patient_id=patient_id, patient_pid=patient_pid, status='QUEUED',
        )
        db.add(q)
        db.flush()
    except Exception as e:
        log.debug('Could not queue SMS: %s', e)


async def _mark_sent(db, phone, message_id):
    if not db:
        return
    try:
        from models.notifications import SMSQueue
        from sqlalchemy import desc
        q = (db.query(SMSQueue)
             .filter(SMSQueue.phone_number == phone, SMSQueue.status == 'QUEUED')
             .order_by(desc(SMSQueue.created_at)).first())
        if q:
            q.status   = 'SENT'
            q.sent_at  = datetime.now(timezone.utc)
            db.flush()
    except Exception:
        pass


# ── High-level helpers ────────────────────────────────────────────────────────

async def notify_result_ready(
    phone: str,
    patient_name: str,
    lid: str,
    hospital_name: str,
    hospital_phone: str = '',
    language: str = 'en',
    db=None,
) -> dict:
    """Notify patient that lab results are ready."""
    template = TEMPLATES['result_ready'].get(language, TEMPLATES['result_ready']['en'])
    message  = template.format(
        patient_name=patient_name,
        lid=lid,
        hospital_name=hospital_name,
        hospital_phone=hospital_phone or '',
        date=datetime.now().strftime('%d %b %Y'),
    )
    return await send_sms(phone, message, 'RESULT_READY', db=db)


async def notify_critical_value(
    clinician_phone: str,
    patient_pid: str,
    test_name: str,
    value: str,
    unit: str,
    flag: str,
    hospital_name: str,
    hospital_phone: str = '',
    db=None,
) -> dict:
    """Alert clinician of a critical lab value — URGENT."""
    template = TEMPLATES['critical_value']['en']
    message  = template.format(
        patient_pid=patient_pid, test_name=test_name,
        value=value, unit=unit, flag=flag,
        hospital_name=hospital_name, hospital_phone=hospital_phone,
    )
    return await send_sms(clinician_phone, message, 'CRITICAL_VALUE', patient_pid=patient_pid, db=db)


async def send_otp(
    phone: str,
    otp_code: str,
    language: str = 'en',
    db=None,
) -> dict:
    """Send 2FA OTP code via SMS."""
    template = TEMPLATES['otp_2fa'].get(language, TEMPLATES['otp_2fa']['en'])
    message  = template.format(otp=otp_code)
    return await send_sms(phone, message, 'OTP', db=db)


async def notify_low_stock(
    manager_phone: str,
    item_name: str,
    remaining: float,
    unit: str,
    reorder_level: float,
    hospital_name: str,
    db=None,
) -> dict:
    template = TEMPLATES['low_stock']['en']
    message  = template.format(
        item_name=item_name, remaining=remaining, unit=unit,
        reorder_level=reorder_level, hospital_name=hospital_name,
    )
    return await send_sms(manager_phone, message, 'LOW_STOCK', db=db)


async def send_shift_reminder(
    phone: str,
    shift_name: str,
    start_time: str,
    hospital_name: str,
    language: str = 'en',
    db=None,
) -> dict:
    template = TEMPLATES['shift_reminder'].get(language, TEMPLATES['shift_reminder']['en'])
    message  = template.format(
        shift_name=shift_name, start_time=start_time, hospital_name=hospital_name,
    )
    return await send_sms(phone, message, 'SHIFT_REMINDER', db=db)
