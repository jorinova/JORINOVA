"""Generic ASTM E1394 result records — many bench analyzers still emit this."""
from __future__ import annotations

from typing import Optional

from . import AnalyzerAdapter, IngestEnvelope, ParsedResult, register


def _decode(env: IngestEnvelope) -> str:
    try:
        return env.raw_payload.decode('ascii', errors='replace')
    except Exception:
        return env.raw_payload.decode('latin-1', errors='replace')


@register('astm_generic')
class AstmGenericAdapter:
    id          = 'astm_generic'
    vendor      = 'Generic'
    model       = 'ASTM E1394 / E1381'
    wire_format = 'ASTM'
    description = 'ASTM E1394 — older but still common on chemistry / urinalysis benches.'

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]:
        text = _decode(env)
        results: list[ParsedResult] = []
        sample_id: Optional[str] = None
        pid:       Optional[str] = None

        # ASTM separators are |, ^, ~ between fields/components/repetitions
        for raw_line in text.replace('\r', '\n').split('\n'):
            line = raw_line.strip().lstrip('\x02').rstrip('\x03')
            if not line or '|' not in line:
                continue
            fields = line.split('|')
            kind = (fields[0] or '')[-1] if fields[0] else ''  # 'P' / 'O' / 'R' …

            if kind == 'P' and len(fields) > 3:
                pid = fields[3].split('^')[0] or None
            elif kind == 'O' and len(fields) > 2:
                sample_id = fields[2].split('^')[0] or None
            elif kind == 'R' and len(fields) > 5:
                # |R|N|^^^TEST^TestName|Value|Unit|RefRange|Flag|...
                test_field = fields[2].split('^') if len(fields) > 2 else []
                code = test_field[3] if len(test_field) > 3 else ''
                name = test_field[4] if len(test_field) > 4 else code
                value = fields[3] if len(fields) > 3 else ''
                unit  = fields[4] if len(fields) > 4 else ''
                ref   = fields[5] if len(fields) > 5 else ''
                flag  = (fields[6] if len(fields) > 6 else '').upper() or None

                ref_low: Optional[float] = None
                ref_high: Optional[float] = None
                if 'to' in ref:
                    parts = [p.strip() for p in ref.split('to')]
                    try: ref_low  = float(parts[0])
                    except Exception: pass
                    try: ref_high = float(parts[1])
                    except Exception: pass

                try: numeric: Optional[float] = float(value)
                except Exception: numeric = None

                results.append(ParsedResult(
                    sample_id      = sample_id,
                    patient_pid    = pid,
                    test_code      = code,
                    test_name      = name,
                    value          = value,
                    numeric_value  = numeric,
                    unit           = unit,
                    flag           = flag if flag in ('H', 'L', 'HH', 'LL', 'POS', 'NEG') else None,
                    reference_low  = ref_low,
                    reference_high = ref_high,
                    instrument     = env.instrument_id,
                    raw_fields     = {'r_segment': fields},
                ))
        return results
