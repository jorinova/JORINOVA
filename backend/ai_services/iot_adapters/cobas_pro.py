"""
Roche Cobas Pro example.

Cobas Pro chemistry analyzers can speak ASTM, HL7, or proprietary Roche
"Cobas Link" payloads. We use ASTM here as the canonical baseline; the
adapter is otherwise a thin wrapper over the generic ASTM adapter that
labels the vendor and normalises the instrument name.
"""
from __future__ import annotations

from . import IngestEnvelope, ParsedResult, register
from .astm_generic import AstmGenericAdapter


@register('cobas_pro')
class CobasProAdapter:
    id          = 'cobas_pro'
    vendor      = 'Roche'
    model       = 'Cobas Pro'
    wire_format = 'ASTM'
    description = 'Roche Cobas Pro chemistry — ASTM E1394 with Cobas vendor naming.'

    def __init__(self) -> None:
        self._base = AstmGenericAdapter()

    def parse(self, env: IngestEnvelope) -> list[ParsedResult]:
        rows = self._base.parse(env)
        for r in rows:
            r.instrument = r.instrument or 'Roche Cobas Pro'
            # Roche frequently emits delta-flag 'D' which is not a result flag.
            if r.flag and r.flag.upper() == 'D':
                r.flag = None
        return rows
