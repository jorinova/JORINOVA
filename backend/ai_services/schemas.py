"""Pydantic schemas shared across all AI services."""
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Task taxonomy ─────────────────────────────────────────────────────────────

class TaskType(str, Enum):
    # Rules-engine tasks (offline, deterministic)
    FLAG_CHECK        = 'flag_check'         # panic value + reference check
    INVENTORY_ALERT   = 'inventory_alert'     # stock threshold rules
    SOP_ALERT         = 'sop_alert'           # SOP-based workflow rules
    REFLEX_SUGGEST    = 'reflex_suggest'      # DB-backed reflex tests

    # Local-LLM tasks (offline, generative)
    VOICE_COMMAND     = 'voice_command'       # parse voice → action
    BASIC_INTERPRET   = 'basic_interpret'     # flag + local context
    REPORT_DRAFT      = 'report_draft'        # short report text
    OFFLINE_ASSISTANT = 'offline_assistant'   # general Q&A offline

    # Cloud-LLM tasks (online, advanced)
    CLINICAL_REASON   = 'clinical_reason'     # complex differential dx
    EPIDEMIC_ANALYSIS = 'epidemic_analysis'   # outbreak intelligence
    DRUG_INTERACTION  = 'drug_interaction'    # polypharmacy check
    ADVANCED_SUMMARY  = 'advanced_summary'    # full panel reasoning
    RESEARCH_ASSIST   = 'research_assist'     # literature/guidelines

    # Vision tasks (async-queued)
    SLIDE_ANALYSIS    = 'slide_analysis'      # microscope image
    SMEAR_ANALYSIS    = 'smear_analysis'      # blood smear
    XRAY_SCREEN       = 'xray_screen'         # CXR TB screening

    # Speech tasks
    SPEECH_TO_TEXT    = 'speech_to_text'      # raw transcription
    COMMAND_PARSE     = 'command_parse'        # NLU → structured action

    # Hybrid
    PANEL_ANALYSIS    = 'panel_analysis'      # multi-result reasoning
    CRITICAL_TRIAGE   = 'critical_triage'     # rules + AI combined

    # Document reading
    READ_DOCUMENT     = 'read_document'       # universal document reader
    OCR_IMAGE         = 'ocr_image'           # image text extraction
    DECODE_BARCODE    = 'decode_barcode'      # barcode / QR decode
    PARSE_INSTRUMENT  = 'parse_instrument'    # analyzer output parser
    EXTRACT_LAB_RESULTS='extract_lab_results' # AI-extract results from report
    ASK_DOCUMENT      = 'ask_document'        # document Q&A


class AILayer(str, Enum):
    RULES  = 'rules_engine'
    LOCAL  = 'local_llm'
    CLOUD  = 'cloud_llm'
    SPEECH = 'speech'
    VISION = 'vision'
    HYBRID = 'hybrid'       # rules → local → cloud waterfall


class Urgency(str, Enum):
    IMMEDIATE = 'IMMEDIATE'   # notify clinician NOW
    URGENT    = 'URGENT'      # within 1 hour
    ROUTINE   = 'ROUTINE'     # standard workflow
    INFO      = 'INFO'        # informational only


# ── AI request/response ───────────────────────────────────────────────────────

class AIRequest(BaseModel):
    task_type:   TaskType
    payload:     dict[str, Any]
    use_cache:   bool = True
    timeout_s:   float = 30.0
    patient_id:  Optional[int] = None
    lab_req_id:  Optional[int] = None
    user_id:     Optional[int] = None


class AIResponse(BaseModel):
    content:     str = ''
    layer_used:  AILayer = AILayer.RULES
    model:       str = 'rules_engine'
    latency_ms:  int = 0
    cached:      bool = False
    error:       str = ''
    metadata:    dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.content) and not self.error

    def to_dict(self) -> dict:
        return self.model_dump()


# ── Rules engine schemas ──────────────────────────────────────────────────────

class PanicAlert(BaseModel):
    test_code:   str
    test_name:   str
    value:       float
    unit:        str
    flag:        str                    # HH | LL | CRITICAL
    threshold:   float
    direction:   str                    # HIGH | LOW
    urgency:     Urgency = Urgency.IMMEDIATE
    message:     str = ''
    actions:     list[str] = Field(default_factory=list)


class RulesResult(BaseModel):
    is_critical:     bool = False
    panic_alerts:    list[PanicAlert] = Field(default_factory=list)
    interpretation:  str = ''
    significance:    str = 'NORMAL'    # CRITICAL|HIGH|MODERATE|LOW|NORMAL
    possible_causes: list[str] = Field(default_factory=list)
    actions:         list[str] = Field(default_factory=list)
    reflex_tests:    list[dict] = Field(default_factory=list)
    doctor_required: bool = False
    doctor_urgency:  str = ''
    sop_notes:       list[str] = Field(default_factory=list)


# ── Speech schemas ────────────────────────────────────────────────────────────

class VoiceCommandAction(str, Enum):
    OPEN_PATIENT     = 'open_patient'
    SEARCH_PATIENT   = 'search_patient'
    VALIDATE_RESULT  = 'validate_result'
    PRINT_REPORT     = 'print_report'
    FLAG_CRITICAL    = 'flag_critical'
    OPEN_MODULE      = 'open_module'
    RUN_REPORT       = 'run_report'
    ADD_NOTE         = 'add_note'
    UNKNOWN          = 'unknown'


class ParsedCommand(BaseModel):
    action:      VoiceCommandAction = VoiceCommandAction.UNKNOWN
    entity:      str = ''           # patient name, module name, etc.
    parameters:  dict[str, str] = Field(default_factory=dict)
    confidence:  float = 0.0
    raw_text:    str = ''


# ── Vision schemas ────────────────────────────────────────────────────────────

class VisionTask(BaseModel):
    task_id:    str
    image_type: str   # smear|slide|xray|gel
    file_path:  str
    patient_id: Optional[int] = None
    lab_req_id: Optional[int] = None
    priority:   str = 'routine'   # stat|routine


class VisionResult(BaseModel):
    task_id:      str
    findings:     list[str] = Field(default_factory=list)
    confidence:   float = 0.0
    layer_used:   str = 'offline'
    raw_output:   dict = Field(default_factory=dict)
    requires_review: bool = True   # always human-in-the-loop


# ── System status ─────────────────────────────────────────────────────────────

class ServiceHealth(BaseModel):
    name:      str
    available: bool
    latency_ms: Optional[int] = None
    model:     Optional[str] = None
    error:     Optional[str] = None


class SystemStatus(BaseModel):
    offline_capable: bool = True     # always True — rules engine never fails
    rules_engine:    ServiceHealth
    local_llm:       ServiceHealth
    cloud_llm:       ServiceHealth
    speech:          ServiceHealth
    vision:          ServiceHealth
    redis:           ServiceHealth
    recommended_layer: AILayer = AILayer.RULES
