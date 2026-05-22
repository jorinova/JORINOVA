"""
Analyzer-agnostic IoT adapter layer
====================================
Every lab analyzer talks a slightly different dialect. This package gives the
LIS one stable contract — `AnalyzerAdapter` — and a registry so we can support
any machine in the lab without touching the routers.

Built-in adapters:

  - hl7_generic   : ASTM-encoded HL7 v2.x ORU^R01 (most common)
  - astm_generic  : ASTM E1394 / E1381 raw text
  - json_push     : modern instruments that POST JSON (Mindray, Roche v3, etc.)
  - csv_dump      : analyzers that drop CSV files into a watch folder
  - sysmex_xn     : example vendor variant of HL7 (Sysmex XN-Series)
  - cobas_pro     : example vendor variant of ASTM (Roche Cobas Pro)

Adding a new analyzer model = drop a new module in this package and decorate
its class with `@register('vendor_model')`. No router or scene changes needed.

Public API
----------
    from ai_services.iot_adapters import (
        AnalyzerAdapter,
        IngestEnvelope,
        ParsedResult,
        list_adapters,
        get_adapter,
        ingest,
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol


# ── Wire shapes ──────────────────────────────────────────────────────────────

@dataclass
class IngestEnvelope:
    """One inbound payload from any analyzer."""
    adapter_id:    str                       # 'hl7_generic', 'sysmex_xn', …
    instrument_id: str                       # serial / inventory id of the box
    raw_payload:   bytes                     # the original bytes from the wire
    content_type:  str = 'application/octet-stream'
    received_at:   Optional[str] = None      # ISO timestamp (set by router if absent)
    source_hint:   dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedResult:
    """Normalised result row. One ParsedResult per test inside a payload."""
    sample_id:        Optional[str]  = None      # SID from the tube barcode
    patient_pid:      Optional[str]  = None
    test_code:        Optional[str]  = None      # mapping target for TestCatalog.code
    test_name:        Optional[str]  = None
    value:            Optional[str]  = None
    numeric_value:    Optional[float] = None
    unit:             Optional[str]  = None
    flag:             Optional[str]  = None      # H | L | HH | LL | POS | NEG | None
    reference_low:    Optional[float] = None
    reference_high:   Optional[float] = None
    result_status:    str = 'PRELIMINARY'        # PRELIMINARY | FINAL | CORRECTED
    instrument:       Optional[str]  = None
    measured_at:      Optional[str]  = None
    raw_fields:       dict[str, Any] = field(default_factory=dict)


# ── Adapter contract ─────────────────────────────────────────────────────────

class AnalyzerAdapter(Protocol):
    """
    Any analyzer adapter only needs to know how to:
      1. say what it is (`id`, `vendor`, `model`, `wire_format`)
      2. accept raw bytes + return a list of ParsedResult rows.
    """
    id:           str
    vendor:       str
    model:        str
    wire_format:  str          # 'HL7v2' | 'ASTM' | 'JSON' | 'CSV'
    description:  str

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]: ...


# ── Registry ────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, AnalyzerAdapter] = {}


def register(adapter_id: str) -> Callable[[type], type]:
    """Class decorator that registers an adapter class instance under the given id."""
    def deco(cls: type) -> type:
        instance = cls()
        # Make sure the class set its own id correctly
        if not getattr(instance, 'id', None):
            instance.id = adapter_id
        _REGISTRY[adapter_id] = instance
        return cls
    return deco


def list_adapters() -> list[dict[str, str]]:
    return [
        {
            'id':           a.id,
            'vendor':       a.vendor,
            'model':        a.model,
            'wire_format':  a.wire_format,
            'description':  a.description,
        }
        for a in _REGISTRY.values()
    ]


def get_adapter(adapter_id: str) -> AnalyzerAdapter | None:
    return _REGISTRY.get(adapter_id)


def ingest(env: IngestEnvelope) -> list[ParsedResult]:
    """
    Top-level entry point used by the router. Validates that we know the
    adapter, then dispatches to it. Never raises on bad payloads — returns
    an empty list and lets the caller report 422.
    """
    adapter = _REGISTRY.get(env.adapter_id)
    if adapter is None:
        return []
    try:
        return adapter.parse(env)
    except Exception:
        # Adapters must be defensive; if they raise, log and yield nothing.
        import logging
        logging.getLogger('alis_x.iot').exception(
            'Adapter %s failed parsing %d bytes from instrument %s',
            env.adapter_id, len(env.raw_payload), env.instrument_id,
        )
        return []


# ── Eager imports (so @register decorators run on package load) ──────────────

from . import hl7_generic    # noqa: F401,E402
from . import astm_generic   # noqa: F401,E402
from . import json_push      # noqa: F401,E402
from . import csv_dump       # noqa: F401,E402
from . import sysmex_xn      # noqa: F401,E402
from . import cobas_pro      # noqa: F401,E402
