"""
Sysmex XN-Series example.

Sysmex hematology analyzers (XN-1000, XN-2000, XN-3000, XN-9100, XN-V) all
emit HL7 v2.5 ORU^R01 with a few vendor quirks:
  - Some firmware uses |R| as the abnormal-flag delta (delta check)
  - Test codes come through as Sysmex shortnames (WBC, RBC, HGB, …) which
    mostly already match TestCatalog.code so we accept as-is.
"""
from __future__ import annotations

from . import IngestEnvelope, ParsedResult, register
from .hl7_generic import Hl7GenericAdapter


@register('sysmex_xn')
class SysmexXnAdapter:
    id          = 'sysmex_xn'
    vendor      = 'Sysmex'
    model       = 'XN-Series (XN-1000 / XN-2000 / XN-3000 / XN-V)'
    wire_format = 'HL7v2'
    description = 'Sysmex XN-Series hematology — HL7 v2.5 ORU^R01 with vendor abnormal-flag handling.'

    def __init__(self) -> None:
        self._base = Hl7GenericAdapter()

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]:
        rows = self._base.parse(env)
        # Vendor tweak: Sysmex sends '!' for panic values. Normalise to 'HH'.
        for r in rows:
            raw_obx = r.raw_fields.get('obx') if isinstance(r.raw_fields, dict) else None
            abnormal = (raw_obx[8] if (isinstance(raw_obx, list) and len(raw_obx) > 8) else '') or ''
            if '!' in abnormal:
                r.flag = 'HH'
            r.instrument = r.instrument or 'Sysmex XN'
        return rows
