"""Generic HL7 v2.x ORU^R01 adapter — covers ~70 % of analyzers in the wild."""
from __future__ import annotations

from typing import Optional

from . import AnalyzerAdapter, IngestEnvelope, ParsedResult, register


def _decode(env: IngestEnvelope) -> str:
    """ASTM/HL7 commonly use ASCII or Latin-1. Try ASCII first, fall back."""
    try:
        return env.raw_payload.decode('ascii', errors='replace')
    except Exception:
        return env.raw_payload.decode('latin-1', errors='replace')


def _segments(text: str) -> list[list[str]]:
    """Split HL7 text into a list of fields-by-segment."""
    out = []
    # HL7 uses CR (\r) as segment terminator but most tools use \n. Accept both.
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = line.strip()
        if not line:
            continue
        out.append(line.split('|'))
    return out


def _flag_from_hl7(abnormal: str) -> Optional[str]:
    m = abnormal.upper().strip()
    if m in ('H', 'L', 'HH', 'LL', 'A', 'N', 'POS', 'NEG'):
        return None if m == 'N' else m
    return None


@register('hl7_generic')
class Hl7GenericAdapter:
    id          = 'hl7_generic'
    vendor      = 'Generic'
    model       = 'HL7 v2.x ORU^R01'
    wire_format = 'HL7v2'
    description = 'Standards-compliant HL7 v2.5+ ORU^R01 — covers most analyzers when set to "HL7" output.'

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]:
        text = _decode(env)
        segs = _segments(text)

        # Sample / patient context — pulled from PID + OBR segments
        pid:       Optional[str] = None
        sample_id: Optional[str] = None
        for s in segs:
            if not s: continue
            if s[0] == 'PID' and len(s) > 3:
                pid = s[3].split('^')[0] or None
            elif s[0] == 'OBR' and len(s) > 3:
                sample_id = s[3].split('^')[0] or None

        results: list[ParsedResult] = []
        for s in segs:
            if not s or s[0] != 'OBX':
                continue
            # OBX: |SetID|ValueType|ObservationId^Code|SubID|Value|Unit|RefRange|AbnormalFlag|...
            if len(s) < 6:
                continue
            code_field = s[3].split('^') if len(s) > 3 else ['']
            code = code_field[0] or ''
            name = code_field[1] if len(code_field) > 1 else code
            value     = s[5] if len(s) > 5 else ''
            unit      = s[6] if len(s) > 6 else ''
            ref_range = s[7] if len(s) > 7 else ''
            abnormal  = s[8] if len(s) > 8 else ''

            ref_low: Optional[float] = None
            ref_high: Optional[float] = None
            if ref_range and '-' in ref_range:
                try:
                    lo, hi = ref_range.split('-', 1)
                    ref_low  = float(lo.strip())
                    ref_high = float(hi.strip())
                except Exception:
                    pass

            try:
                numeric: Optional[float] = float(value)
            except Exception:
                numeric = None

            results.append(ParsedResult(
                sample_id      = sample_id,
                patient_pid    = pid,
                test_code      = code,
                test_name      = name,
                value          = value,
                numeric_value  = numeric,
                unit           = unit,
                flag           = _flag_from_hl7(abnormal),
                reference_low  = ref_low,
                reference_high = ref_high,
                result_status  = 'FINAL',
                instrument     = env.instrument_id,
                raw_fields     = {'obx': s},
            ))
        return results
