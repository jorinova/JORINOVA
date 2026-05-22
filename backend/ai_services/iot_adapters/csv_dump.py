"""CSV result dumps — typical of older urinalysis / coag instruments."""
from __future__ import annotations

import csv
import io
from typing import Optional

from . import AnalyzerAdapter, IngestEnvelope, ParsedResult, register


@register('csv_dump')
class CsvDumpAdapter:
    id          = 'csv_dump'
    vendor      = 'Generic'
    model       = 'CSV file dump'
    wire_format = 'CSV'
    description = 'Watch-folder CSV: any analyzer that writes a CSV file per run.'

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]:
        try:
            text = env.raw_payload.decode('utf-8-sig', errors='replace')
        except Exception:
            text = env.raw_payload.decode('latin-1', errors='replace')

        reader = csv.DictReader(io.StringIO(text))
        out: list[ParsedResult] = []
        for row in reader:
            v = (row.get('value') or row.get('Value') or '').strip()
            num: Optional[float] = None
            try: num = float(v)
            except Exception: pass
            flag = (row.get('flag') or row.get('Flag') or '').upper().strip() or None
            out.append(ParsedResult(
                sample_id     = row.get('sample_id') or row.get('SampleID'),
                patient_pid   = row.get('pid') or row.get('PID'),
                test_code     = row.get('test_code') or row.get('Test') or row.get('test'),
                test_name     = row.get('test_name') or row.get('TestName'),
                value         = v or None,
                numeric_value = num,
                unit          = row.get('unit') or row.get('Unit'),
                flag          = flag if flag in ('H', 'L', 'HH', 'LL', 'POS', 'NEG') else None,
                instrument    = row.get('instrument') or env.instrument_id,
                measured_at   = row.get('measured_at') or row.get('Timestamp'),
                raw_fields    = dict(row),
            ))
        return out
