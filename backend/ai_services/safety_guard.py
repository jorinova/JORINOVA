"""
ALIS-X Safety Guard
===================
Implements the safety-first AI policy:

  1. AI handles ANY user command (not just predefined lab actions)
  2. If a command could cause harm → AI WARNS the user first
  3. If user persists after warning → AI ESCALATES to Head of Department
  4. HoD must APPROVE before the dangerous action proceeds
  5. All safety events are permanently AUDITED

Danger taxonomy (4 levels):
  SAFE        → execute immediately
  CAUTION     → warn once, allow if user confirms
  DANGEROUS   → warn strongly, require explicit confirmation, log
  BLOCKED     → refuse entirely, escalate to HoD automatically

Examples:
  "Open laboratory module"          → SAFE
  "Delete a test result"            → CAUTION
  "Modify a validated critical result" → DANGEROUS
  "Delete all patient records"      → BLOCKED + immediate escalation
  "Export all patient data"         → DANGEROUS
  "Bypass calibration check"        → DANGEROUS
  "Release result without validation" → DANGEROUS

The AI also handles general conversational commands — questions about
patient care, procedure guidance, equipment, general knowledge — anything
the user asks. It just applies safety filtering first.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger('safety_guard')


# ── Danger level ──────────────────────────────────────────────────────────────

class DangerLevel(str, Enum):
    SAFE      = 'safe'
    CAUTION   = 'caution'
    DANGEROUS = 'dangerous'
    BLOCKED   = 'blocked'


@dataclass
class SafetyAssessment:
    level:          DangerLevel
    category:       str        = ''       # e.g. 'result_manipulation'
    warning_text:   str        = ''       # human-readable warning
    warning_lang:   str        = 'en'
    requires_confirmation: bool = False
    requires_hod:   bool       = False    # escalate to Head of Department
    action_allowed: bool       = True
    reason:         str        = ''       # for audit log
    alternatives:   list[str]  = field(default_factory=list)


# ── Danger patterns (coded rules — offline, zero-latency) ────────────────────
# Each entry: (regex pattern, DangerLevel, category, warning)

_DANGER_PATTERNS: list[tuple] = [
    # ── BLOCKED ────────────────────────────────────────────────────────────
    (re.compile(r'\b(delete|remove|erase|wipe).{0,30}(all|every|batch).{0,30}(patient|record|result|data)\b', re.I),
     DangerLevel.BLOCKED, 'mass_deletion',
     'This would permanently delete multiple patient records. This action is prohibited and requires HoD authorisation.',
     ['Contact the Head of Department directly', 'Use the data archival function instead']),

    (re.compile(r'\b(drop|truncate|delete from).{0,15}(table|database|db)\b', re.I),
     DangerLevel.BLOCKED, 'database_destruction',
     'Database destruction commands are permanently blocked in ALIS-X.',
     ['Contact your system administrator']),

    (re.compile(r'\b(bypass|skip|ignore|disable).{0,20}(audit|log|security|auth|authentication)\b', re.I),
     DangerLevel.BLOCKED, 'security_bypass',
     'Bypassing security and audit systems is strictly prohibited.',
     ['All actions in ALIS-X are permanently audited by design']),

    (re.compile(r'\b(export|download|dump|extract).{0,20}(all|every|bulk|batch).{0,20}(patient|record|pii|personal)\b', re.I),
     DangerLevel.BLOCKED, 'bulk_data_export',
     'Bulk export of patient data is blocked. Patient privacy is protected by law.',
     ['Request individual records through proper authorization channels',
      'For research: use the anonymized data export with ethics approval']),

    # ── DANGEROUS ───────────────────────────────────────────────────────────
    (re.compile(r'\b(modify|change|alter|edit|update).{0,30}(validated|final|released|critical)\s+result\b', re.I),
     DangerLevel.DANGEROUS, 'modify_validated_result',
     'Modifying a validated or released result is a high-risk action with medico-legal implications. An amended report must be issued with reason.',
     ['Issue an amended report with reason', 'Consult the laboratory manager first']),

    (re.compile(r'\b(delete|remove|cancel).{0,20}(result|test|sample|specimen)\b', re.I),
     DangerLevel.DANGEROUS, 'delete_result',
     'Deleting a laboratory result permanently removes it from the audit trail. This requires justification.',
     ['Cancel the test order instead', 'Add a rejection note with reason']),

    (re.compile(r'\b(release|send|deliver|publish|finalize).{0,30}result.{0,25}(without|no|skip|bypass).{0,25}(validat|approv|check)', re.I),
     DangerLevel.DANGEROUS, 'release_without_validation',
     'Releasing a result without validation is a laboratory SOP violation. Results must be validated before release.',
     ['Complete the validation step first', 'Request expedited validation if urgent']),

    (re.compile(r'\b(bypass|skip|override|ignore|skip).{0,25}(calibrat|quality.control|qc\b|q\.c\.)', re.I),
     DangerLevel.DANGEROUS, 'bypass_qc',
     'Bypassing quality control could lead to incorrect patient results. This is an ISO 15189 violation.',
     ['Complete the QC run first', 'Document QC failure and inform supervisor']),

    (re.compile(r'\b(override|ignore|dismiss).{0,20}(critical|panic|flag|alert)\b', re.I),
     DangerLevel.DANGEROUS, 'ignore_critical_flag',
     'Ignoring a critical value alert without clinical acknowledgement is a patient safety risk.',
     ['Notify the clinician first', 'Document the acknowledgement in the critical book']),

    (re.compile(r'\b(transfuse|give|administer).{0,30}(without|no).{0,20}(crossmatch|compat|group)\b', re.I),
     DangerLevel.DANGEROUS, 'transfusion_without_crossmatch',
     'Transfusion without crossmatch is a life-threatening risk. Emergency uncrossmatched blood protocols exist for this.',
     ['Follow emergency uncrossmatched blood protocol', 'Notify blood bank and haematologist immediately']),

    (re.compile(r'\b(share|send|give).{0,20}patient.{0,20}(record|data|result).{0,20}(outside|external|unauthor)\b', re.I),
     DangerLevel.DANGEROUS, 'unauthorised_data_sharing',
     'Sharing patient data with unauthorised parties is a GDPR/patient rights violation.',
     ['Use the controlled inter-hospital access system', 'Obtain written patient consent first']),

    # ── CAUTION ─────────────────────────────────────────────────────────────
    (re.compile(r'\b(undo|revert|cancel)\s+(result|test|order)\b', re.I),
     DangerLevel.CAUTION, 'undo_action',
     'Reverting or cancelling a result will create an audit trail entry. Please confirm this is intentional.',
     ['Document the reason for cancellation']),

    (re.compile(r'\b(close|discharge|archive)\s+patient\b', re.I),
     DangerLevel.CAUTION, 'discharge_patient',
     'Archiving or discharging a patient will make their record read-only. Confirm this is correct.',
     ['Ensure all results are validated first']),

    (re.compile(r'\b(transfer|move)\s+(blood|specimen|sample).{0,30}(another|different)\b', re.I),
     DangerLevel.CAUTION, 'inter_hospital_transfer',
     'Specimen transfer requires documented chain of custody. Please confirm.',
     ['Ensure transfer documentation is complete']),
]


# ── Repeat-attempt tracker ────────────────────────────────────────────────────
# Tracks how many times a user has attempted a dangerous action
# Format: key = (user_id, category, hash) → (count, first_attempt_epoch)

_repeat_tracker: dict[str, tuple[int, float]] = {}
_REPEAT_WINDOW_S = 300    # 5 minutes — window to count repeats
_ESCALATE_AFTER  = 1      # escalate on second attempt (after one warning)


def _repeat_key(user_id: int, category: str, command_hash: str) -> str:
    return f'{user_id}:{category}:{command_hash[:16]}'


def _record_attempt(user_id: int, category: str, cmd_hash: str) -> int:
    """Record a dangerous command attempt. Returns attempt count in window."""
    key = _repeat_key(user_id, category, cmd_hash)
    now = time.time()
    count, first = _repeat_tracker.get(key, (0, now))
    if now - first > _REPEAT_WINDOW_S:
        count, first = 0, now
    count += 1
    _repeat_tracker[key] = (count, first)
    return count


def _clear_attempt(user_id: int, category: str, cmd_hash: str) -> None:
    key = _repeat_key(user_id, category, cmd_hash)
    _repeat_tracker.pop(key, None)


# ── Public API ────────────────────────────────────────────────────────────────

def assess_command(
    command:  str,
    user_id:  int = 0,
    user_role:str = '',
    lang:     str = 'en',
) -> SafetyAssessment:
    """
    Assess the safety level of a user command.
    Runs offline — pattern matching only, zero latency.
    Returns SafetyAssessment with level, warning, and action guidance.
    """
    import hashlib
    cmd_hash = hashlib.sha256(command.encode()).hexdigest()[:16]
    command_lower = command.lower().strip()

    for pattern, level, category, warning, alternatives in _DANGER_PATTERNS:
        if pattern.search(command_lower):
            attempt_count = _record_attempt(user_id, category, cmd_hash)

            if level == DangerLevel.BLOCKED:
                return SafetyAssessment(
                    level          = DangerLevel.BLOCKED,
                    category       = category,
                    warning_text   = warning,
                    warning_lang   = lang,
                    requires_confirmation = False,
                    requires_hod   = True,
                    action_allowed = False,
                    reason         = f'Blocked command: {category}',
                    alternatives   = alternatives,
                )

            if level == DangerLevel.DANGEROUS:
                if attempt_count > _ESCALATE_AFTER:
                    # User has persisted after warning → escalate to HoD
                    return SafetyAssessment(
                        level          = DangerLevel.DANGEROUS,
                        category       = category,
                        warning_text   = _persist_warning(lang),
                        warning_lang   = lang,
                        requires_confirmation = False,
                        requires_hod   = True,
                        action_allowed = False,
                        reason         = f'User persisted after warning: {category} (attempt {attempt_count})',
                        alternatives   = alternatives,
                    )
                return SafetyAssessment(
                    level          = DangerLevel.DANGEROUS,
                    category       = category,
                    warning_text   = warning,
                    warning_lang   = lang,
                    requires_confirmation = True,
                    requires_hod   = False,
                    action_allowed = False,   # blocked until confirmed
                    reason         = f'Dangerous command: {category}',
                    alternatives   = alternatives,
                )

            if level == DangerLevel.CAUTION:
                return SafetyAssessment(
                    level          = DangerLevel.CAUTION,
                    category       = category,
                    warning_text   = warning,
                    warning_lang   = lang,
                    requires_confirmation = True,
                    requires_hod   = False,
                    action_allowed = False,
                    reason         = f'Caution: {category}',
                    alternatives   = alternatives,
                )

    # No pattern matched → SAFE
    return SafetyAssessment(
        level          = DangerLevel.SAFE,
        action_allowed = True,
    )


def confirm_proceed(user_id: int, category: str, cmd_hash: str) -> None:
    """
    User has explicitly confirmed a CAUTION/DANGEROUS action.
    Clears the repeat tracker and allows the action to proceed.
    """
    _clear_attempt(user_id, category, cmd_hash)
    logger.info('User %s confirmed dangerous action: %s', user_id, category)


async def handle_general_command(
    command:   str,
    user_id:   int = 0,
    user_role: str = '',
    lang:      str = 'en',
    context:   str = '',
) -> dict:
    """
    Handle ANY user command using the AI.
    Safety assessment runs FIRST, always.
    Returns: {response, safety, layer, language}
    """
    # 1. Safety assessment (always offline, always first)
    safety = assess_command(command, user_id, user_role, lang)

    response_text = ''
    layer         = 'rules_engine'

    if safety.level == DangerLevel.BLOCKED:
        response_text = safety.warning_text
        return {
            'response':   response_text,
            'safety':     safety.__dict__,
            'layer':      'safety_guard',
            'language':   lang,
            'action':     'blocked',
            'alternatives': safety.alternatives,
        }

    if safety.level in (DangerLevel.DANGEROUS, DangerLevel.CAUTION) and not safety.action_allowed:
        response_text = safety.warning_text
        return {
            'response':   response_text,
            'safety':     safety.__dict__,
            'layer':      'safety_guard',
            'language':   lang,
            'action':     'warn_and_confirm',
            'alternatives': safety.alternatives,
        }

    # 2. Command is SAFE (or CAUTION confirmed) → route to AI
    from ai_services.local_llm import generate as local_gen, is_available as ollama_ok
    from ai_services.cloud_llm import generate as cloud_gen, is_available as cloud_ok

    system_prompt = _build_general_system_prompt(user_role, lang, context)
    prompt        = command

    # Try local LLM first (offline capable)
    if await ollama_ok():
        resp = await local_gen(prompt, system=system_prompt, max_tokens=400, timeout_s=15.0)
        if resp.ok:
            response_text = resp.content
            layer         = 'local_llm'

    # Cloud LLM for better quality (if online)
    if not response_text and await cloud_ok():
        resp = await cloud_gen(prompt, max_tokens=600)
        if resp.ok:
            response_text = resp.content
            layer         = 'cloud_llm'

    # Fallback: rules-based response
    if not response_text:
        response_text = _coded_fallback_response(command, lang)
        layer         = 'coded_fallback'

    # 3. Translate response to user language if needed
    if lang not in ('en', ''):
        from ai_services.language_service import translate_response_to_user_lang
        response_text = await translate_response_to_user_lang(response_text, lang)

    return {
        'response':   response_text,
        'safety':     {'level': safety.level, 'category': safety.category},
        'layer':      layer,
        'language':   lang,
        'action':     'executed',
    }


# ── HoD escalation creation ───────────────────────────────────────────────────

async def create_escalation(
    user_id:     int,
    user_name:   str,
    user_role:   str,
    command:     str,
    category:    str,
    reason:      str,
    db=None,
) -> dict:
    """
    Create a Head of Department escalation record.
    Stores in DB and sends notification.
    Returns the escalation record.
    """
    if db is None:
        logger.error('Cannot create escalation without DB session')
        return {'error': 'Database unavailable for escalation'}

    try:
        from models.escalation import EscalationRecord, EscalationStatus
        from datetime import datetime, timezone

        record = EscalationRecord(
            user_id      = user_id,
            user_name    = user_name,
            user_role    = user_role,
            command_text = command[:500],
            danger_category = category,
            reason       = reason[:500],
            status       = EscalationStatus.PENDING,
            created_at   = datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        logger.warning('ESCALATION CREATED: id=%s user=%s category=%s', record.id, user_name, category)

        # Notify HoD (background — non-blocking)
        import asyncio
        asyncio.create_task(_notify_hod(record.id, user_name, category, command[:200]))

        return {
            'escalation_id': record.id,
            'status':        'pending_hod_approval',
            'message':       'Request sent to Head of Department for authorization.',
        }
    except Exception as e:
        logger.error('Escalation creation failed: %s', e)
        return {'error': str(e)}


async def _notify_hod(
    escalation_id: int,
    user_name:     str,
    category:      str,
    command:       str,
) -> None:
    """Send notification to Head of Department (non-blocking)."""
    try:
        from core.database import SessionLocal
        from models.user import User
        db = SessionLocal()
        hods = db.query(User).filter(
            User.role.in_(['lab_manager', 'head_of_department', 'pathologist', 'super_admin']),
            User.is_active == True,
        ).all()
        for hod in hods:
            logger.warning(
                'ESCALATION NOTIFICATION → %s (%s): User %s attempted [%s]: %s',
                hod.username, hod.role, user_name, category, command[:80],
            )
            # In production: send SMS, email, or in-app notification here
        db.close()
    except Exception as e:
        logger.error('HoD notification error: %s', e)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _persist_warning(lang: str) -> str:
    from ai_services.language_service import get_string
    return get_string(lang, 'persist_warning',
                      'You have persisted in this request. I am now notifying the Head of Department.')


def _build_general_system_prompt(user_role: str, lang: str, context: str) -> str:
    return (
        f'You are ALIS-X, the intelligent assistant for JORINOVA NEXUS hospital laboratory system in Rwanda. '
        f'The user is a {user_role or "laboratory staff member"}. '
        f'You can answer ANY question or help with ANY task within ethical boundaries. '
        f'For laboratory questions: give precise, evidence-based guidance. '
        f'For general questions: answer helpfully and concisely. '
        f'For requests that seem harmful or dangerous: advise against them clearly. '
        f'Respond in {lang if lang != "en" else "English"}. '
        f'Be concise, professional, and human-centred. '
        f'Never pretend you cannot do something — explain what you can do instead. '
        f'{"Context: " + context if context else ""}'
    )


def _coded_fallback_response(command: str, lang: str) -> str:
    """Minimal response when AI is unavailable."""
    from ai_services.language_service import get_string
    return get_string(
        lang, 'offline_mode',
        'I am currently running in offline mode. I can still help with '
        'critical result flagging, inventory alerts, and voice commands. '
        'For complex requests, please reconnect to the network.'
    )
