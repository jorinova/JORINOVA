"""Modern analyzers that POST JSON. Designed to accept either:
   { results: [ {sample_id, test, value, unit, flag, …}, … ] }
   or a single { ... } record.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from . import AnalyzerAdapter, IngestEnvelope, ParsedResult, register


@register('json_push')
class JsonPushAdapter:
    id          = 'json_push'
    vendor      = 'Generic'
    model       = 'JSON push (REST)'
    wire_format = 'JSON'
    description = 'Vendor-neutral JSON: any analyzer that can POST result records over HTTP.'

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]:
        try:
            data: Any = json.loads(env.raw_payload.decode('utf-8'))
        except Exception:
            return []

        rows: list[dict] = []
        if isinstance(data, dict) and isinstance(data.get('results'), list):
            rows = data['results']
        elif isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = [data]

        out: list[ParsedResult] = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            num: Optional[float] = None
            v = r.get('value')
            if v is not None:
                try: num = float(v)
                except Exception: num = None
            flag = (r.get('flag') or '').upper() or None
            out.append(ParsedResult(
                sample_id      = r.get('sample_id') or r.get('sid'),
                patient_pid    = r.get('patient_pid') or r.get('pid'),
                test_code      = r.get('test_code') or r.get('test'),
                test_name      = r.get('test_name') or r.get('name'),
                value          = None if v is None else str(v),
                numeric_value  = num,
                unit           = r.get('unit'),
                flag           = flag if flag in ('H', 'L', 'HH', 'LL', 'POS', 'NEG') else None,
                reference_low  = _to_float(r.get('reference_low') or r.get('ref_low')),
                reference_high = _to_float(r.get('reference_high') or r.get('ref_high')),
                result_status  = (r.get('status') or 'FINAL').upper(),
                instrument     = r.get('instrument') or env.instrument_id,
                measured_at    = r.get('measured_at') or r.get('timestamp'),
                raw_fields     = r,
            ))
        return out


def _to_float(x: Any) -> Optional[float]:
    if x is None: return None
    try: return float(x)
    except Exception: return None
