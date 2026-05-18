"""
ALIS-X Lab Instrument Output Parser
=====================================
Reads and parses output files from laboratory analyzers.

Supported formats:
  - Astm      : ASTM E1394 / LIS2-A2 (universal lab interface)
  - CSV/TXT   : Generic comma/tab delimited (most analyzers)
  - HL7 v2    : ORU^R01 result messages (hospital-grade)
  - FHIR JSON : DiagnosticReport resources (modern systems)
  - Beckman   : Beckman Coulter AU/DXC CSV
  - Sysmex    : Sysmex XN-series export format
  - ABX Pentra: Horiba ABX Pentra CSV
  - Cobas     : Roche Cobas flat-file format
  - GeneXpert : Cepheid GeneXpert XML/CSV

Design: Each parser returns list[InstrumentResult] — normalized results
        that feed directly into the lab result entry system.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger('instrument_parser')


@dataclass
class InstrumentResult:
    """A single test result from an analyzer."""
    test_code:      str
    test_name:      str
    value:          str
    numeric_value:  Optional[float] = None
    unit:           str = ''
    reference_min:  Optional[float] = None
    reference_max:  Optional[float] = None
    reference_text: str = ''
    flag:           str = 'N'       # N|H|L|HH|LL|POS|NEG|A
    result_source:  str = 'AUTOMATED'
    instrument_id:  str = ''
    patient_id:     str = ''
    sample_id:      str = ''
    run_id:         str = ''
    result_dt:      str = ''
    status:         str = 'FINAL'   # PRELIMINARY|FINAL|CORRECTED
    comment:        str = ''
    raw_line:       str = ''

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ParseResult:
    ok:       bool
    results:  list[InstrumentResult] = field(default_factory=list)
    format:   str = ''
    instrument_id: str = ''
    run_id:   str = ''
    sample_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'ok':        self.ok,
            'results':   [r.to_dict() for r in self.results],
            'format':    self.format,
            'instrument':self.instrument_id,
            'sample_ids':self.sample_ids,
            'metadata':  self.metadata,
            'errors':    self.errors,
            'warnings':  self.warnings,
        }


# ── Flag normalisation ────────────────────────────────────────────────────────

_FLAG_MAP = {
    'H': 'H', 'HIGH': 'H', '>': 'H', 'HI': 'H',
    'L': 'L', 'LOW': 'L',  '<': 'L', 'LO': 'L',
    'HH': 'HH', 'H*': 'HH', 'CRITICAL HIGH': 'HH', 'PANIC HIGH': 'HH',
    'LL': 'LL', 'L*': 'LL', 'CRITICAL LOW':  'LL', 'PANIC LOW':  'LL',
    'N': 'N', 'NORMAL': 'N', 'IN': 'N', 'NL': 'N', '': 'N',
    'P': 'POS', 'POS': 'POS', 'POSITIVE': 'POS', 'REACTIVE': 'POS', 'DETECTED': 'POS',
    'NEG': 'NEG', 'NEGATIVE': 'NEG', 'NR': 'NEG', 'NON-REACTIVE': 'NEG', 'NOT DETECTED': 'NEG',
    'A': 'A', 'ABNORMAL': 'A',
}

def _norm_flag(raw: str) -> str:
    return _FLAG_MAP.get((raw or '').strip().upper(), 'A' if raw.strip() else 'N')


def _to_float(s: str) -> Optional[float]:
    try:
        return float(re.sub(r'[^0-9.\-]', '', s))
    except Exception:
        return None


# ── Generic CSV parser ────────────────────────────────────────────────────────

def parse_generic_csv(
    content: str,
    delimiter: str = ',',
    instrument_id: str = '',
) -> ParseResult:
    """
    Parse generic CSV/TSV output from any analyzer.
    Auto-detects column mapping from headers.
    """
    results = []
    errors  = []

    try:
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]

        # Flexible column mapping
        col = _map_columns(headers)

        for row_num, row in enumerate(reader, 2):
            row = {k.strip().lower(): (v or '').strip() for k, v in row.items()}
            try:
                test_code  = row.get(col.get('code', ''), '')
                test_name  = row.get(col.get('name', ''), test_code)
                value      = row.get(col.get('value', ''), '')
                unit       = row.get(col.get('unit', ''), '')
                flag_raw   = row.get(col.get('flag', ''), '')
                ref        = row.get(col.get('ref', ''), '')
                sample_id  = row.get(col.get('sid', ''), '')
                patient_id = row.get(col.get('pid', ''), '')
                result_dt  = row.get(col.get('date', ''), '')
                comment    = row.get(col.get('comment', ''), '')

                if not (test_name or test_code) or not value:
                    continue

                # Parse reference range
                ref_min, ref_max, ref_text = _parse_ref_range(ref)

                results.append(InstrumentResult(
                    test_code     = test_code or test_name.upper()[:10],
                    test_name     = test_name,
                    value         = value,
                    numeric_value = _to_float(value),
                    unit          = unit,
                    reference_min = ref_min,
                    reference_max = ref_max,
                    reference_text= ref_text,
                    flag          = _norm_flag(flag_raw),
                    instrument_id = instrument_id,
                    sample_id     = sample_id,
                    patient_id    = patient_id,
                    result_dt     = result_dt,
                    comment       = comment,
                    raw_line      = str(row),
                ))
            except Exception as e:
                errors.append(f'Row {row_num}: {e}')

        return ParseResult(
            ok=True, results=results, format='generic_csv',
            instrument_id=instrument_id,
            sample_ids=list({r.sample_id for r in results if r.sample_id}),
            errors=errors,
        )
    except Exception as e:
        return ParseResult(ok=False, format='generic_csv', errors=[str(e)])


def _map_columns(headers: list[str]) -> dict[str, str]:
    """Map semantic column names from varied CSV headers."""
    mapping: dict[str, str] = {}
    candidates = {
        'code':    ['test code', 'test_code', 'code', 'testcode', 'analyte code', 'result code'],
        'name':    ['test name', 'test_name', 'analyte', 'analyte name', 'parameter', 'test', 'name'],
        'value':   ['result', 'value', 'result value', 'measured value', 'result_value', 'val'],
        'unit':    ['unit', 'units', 'result unit', 'uom'],
        'flag':    ['flag', 'status', 'abnormal flag', 'result flag', 'hi/lo', 'hilo', 'interpretation'],
        'ref':     ['reference', 'ref range', 'reference range', 'normal range', 'ref', 'normal values'],
        'sid':     ['sample id', 'sample_id', 'sid', 'specimen', 'accession', 'barcode'],
        'pid':     ['patient id', 'patient_id', 'pid', 'patient no', 'medical record'],
        'date':    ['date', 'result date', 'date time', 'result time', 'datetime'],
        'comment': ['comment', 'note', 'remark', 'notes', 'additional info'],
    }
    for key, synonyms in candidates.items():
        for header in headers:
            if header in synonyms:
                mapping[key] = header
                break
            if any(s in header for s in synonyms[:3]):
                mapping[key] = header
                break
    return mapping


# ── ASTM E1394 parser ─────────────────────────────────────────────────────────

def parse_astm(content: str, instrument_id: str = '') -> ParseResult:
    """
    Parse ASTM E1394 / LIS2-A2 protocol messages.
    Universal standard for many clinical analyzers.
    Record types: H(header), P(patient), O(order), R(result), L(terminator)
    """
    results   = []
    errors    = []
    patient   = {}
    order     = {}
    cur_sid   = ''

    for line in re.split(r'[\r\n]+', content.strip()):
        if not line.strip():
            continue
        fields = line.split('|')
        record_type = fields[0] if fields else ''

        if record_type.startswith('H'):          # Header
            instrument_id = fields[4].strip() if len(fields) > 4 else instrument_id
        elif record_type.startswith('P'):        # Patient
            patient = {
                'pid':  fields[2].strip() if len(fields) > 2 else '',
                'name': fields[5].strip() if len(fields) > 5 else '',
                'dob':  fields[7].strip() if len(fields) > 7 else '',
                'sex':  fields[8].strip() if len(fields) > 8 else '',
            }
        elif record_type.startswith('O'):        # Order
            cur_sid = fields[2].strip() if len(fields) > 2 else ''
            order   = {'sid': cur_sid, 'test': fields[4].strip() if len(fields) > 4 else ''}
        elif record_type.startswith('R'):        # Result
            try:
                test_id    = fields[2].strip() if len(fields) > 2 else ''
                value      = fields[3].strip() if len(fields) > 3 else ''
                unit       = fields[4].strip() if len(fields) > 4 else ''
                ref        = fields[5].strip() if len(fields) > 5 else ''
                flag_raw   = fields[6].strip() if len(fields) > 6 else ''
                result_dt  = fields[12].strip() if len(fields) > 12 else ''

                ref_min, ref_max, ref_text = _parse_ref_range(ref)

                # ASTM test_id format: ^^^TESTCODE^TESTNAME
                parts     = test_id.split('^')
                test_code = parts[3].strip() if len(parts) > 3 else test_id
                test_name = parts[4].strip() if len(parts) > 4 else test_code

                if value:
                    results.append(InstrumentResult(
                        test_code     = test_code,
                        test_name     = test_name,
                        value         = value,
                        numeric_value = _to_float(value),
                        unit          = unit,
                        reference_min = ref_min,
                        reference_max = ref_max,
                        reference_text= ref_text,
                        flag          = _norm_flag(flag_raw),
                        instrument_id = instrument_id,
                        sample_id     = cur_sid,
                        patient_id    = patient.get('pid', ''),
                        result_dt     = result_dt,
                        raw_line      = line,
                    ))
            except Exception as e:
                errors.append(f'ASTM R-record: {e}')

    return ParseResult(
        ok=True, results=results, format='astm',
        instrument_id=instrument_id,
        sample_ids=list({r.sample_id for r in results if r.sample_id}),
        metadata={'patient': patient},
        errors=errors,
    )


# ── GeneXpert XML parser ──────────────────────────────────────────────────────

def parse_genexpert_xml(content: str) -> ParseResult:
    """
    Parse Cepheid GeneXpert XML export.
    Extracts MTB result, RIF resistance, semi-quantification, Ct values.
    """
    results = []
    errors  = []
    try:
        root = ET.fromstring(content)
        ns   = {'gx': root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''}

        def _find(node, path):
            for p in [path, f'gx:{path}']:
                found = node.find(p, ns)
                if found is not None:
                    return found
            return None

        def _text(node, path, default=''):
            n = _find(node, path)
            return (n.text or default).strip() if n is not None else default

        cartridge   = root.find('.//Cartridge') or root
        sample_id   = _text(cartridge, 'SampleID')
        instrument  = _text(cartridge, 'InstrumentSN')
        result_dt   = _text(cartridge, 'EndTime')

        # MTB Detection
        mtb_result   = _text(cartridge, 'Result') or _text(cartridge, 'MTBResult')
        rif_result   = _text(cartridge, 'RIFResult') or _text(cartridge, 'RIFResistance')
        semi_quant   = _text(cartridge, 'SemiQuantResult') or _text(cartridge, 'Quantitation')

        # Probes / Ct values
        probes = []
        for probe in root.findall('.//Probe') + root.findall('.//AnalyteResult'):
            probe_name = _text(probe, 'AnalyteName') or _text(probe, 'Name')
            ct_val     = _text(probe, 'Ct') or _text(probe, 'CycleThreshold')
            if probe_name:
                probes.append({'name': probe_name, 'ct': ct_val})

        # Map result to flag
        mtb_upper = mtb_result.upper()
        if 'DETECTED' in mtb_upper and 'NOT' not in mtb_upper:
            flag = 'POS'
        elif 'NOT DETECTED' in mtb_upper or 'NEGATIVE' in mtb_upper:
            flag = 'NEG'
        else:
            flag = 'A'

        # MTB result entry
        results.append(InstrumentResult(
            test_code    = 'MTB_PCR',
            test_name    = 'GeneXpert MTB/RIF Ultra',
            value        = mtb_result,
            unit         = '',
            flag         = flag,
            instrument_id= instrument,
            sample_id    = sample_id,
            result_dt    = result_dt,
            comment      = f'RIF: {rif_result} | Semi-quant: {semi_quant}',
            raw_line     = f'MTB:{mtb_result}',
        ))

        # RIF resistance entry
        if rif_result:
            rif_upper = rif_result.upper()
            rif_flag  = 'POS' if 'DETECTED' in rif_upper and 'NOT' not in rif_upper else 'NEG'
            results.append(InstrumentResult(
                test_code='RIF_RESIST', test_name='Rifampicin Resistance',
                value=rif_result, flag=rif_flag,
                instrument_id=instrument, sample_id=sample_id, result_dt=result_dt,
            ))

        # Ct values
        for p in probes:
            if p['ct']:
                results.append(InstrumentResult(
                    test_code=f'CT_{p["name"].replace(" ","_").upper()[:10]}',
                    test_name=f'Ct: {p["name"]}',
                    value=p['ct'], unit='cycles', flag='N',
                    instrument_id=instrument, sample_id=sample_id, result_dt=result_dt,
                ))

        return ParseResult(
            ok=True, results=results, format='genexpert_xml',
            instrument_id=instrument, sample_ids=[sample_id],
            metadata={'mtb': mtb_result, 'rif': rif_result, 'semi_quant': semi_quant},
        )
    except Exception as e:
        return ParseResult(ok=False, format='genexpert_xml', errors=[str(e)])


# ── FHIR DiagnosticReport parser ─────────────────────────────────────────────

def parse_fhir_diagnostic_report(content: str) -> ParseResult:
    """
    Parse HL7 FHIR R4 DiagnosticReport JSON.
    Used by modern hospital systems, RHIS integrations.
    """
    results = []
    try:
        report = json.loads(content)
        if report.get('resourceType') != 'DiagnosticReport':
            return ParseResult(ok=False, format='fhir',
                               errors=['Not a DiagnosticReport FHIR resource'])

        contained   = {r.get('id', ''): r for r in report.get('contained', [])}
        sample_id   = ''
        patient_id  = ''

        # Extract observations from results
        for ref in report.get('result', []):
            obs_ref = ref.get('reference', '')
            obs_id  = obs_ref.lstrip('#')
            obs     = contained.get(obs_id, {})
            if not obs:
                continue

            code_system = obs.get('code', {})
            test_code   = (code_system.get('coding', [{}])[0].get('code', ''))
            test_name   = (code_system.get('text', '') or
                           code_system.get('coding', [{}])[0].get('display', ''))

            # Value extraction
            val_qty   = obs.get('valueQuantity', {})
            val_str   = obs.get('valueString', '')
            val_coded = obs.get('valueCodeableConcept', {}).get('text', '')
            value     = str(val_qty.get('value', val_str or val_coded))
            unit      = val_qty.get('unit', '')

            # Reference range
            ref_range = obs.get('referenceRange', [{}])[0] if obs.get('referenceRange') else {}
            ref_low   = ref_range.get('low', {}).get('value')
            ref_high  = ref_range.get('high', {}).get('value')
            ref_text  = ref_range.get('text', '')

            # Interpretation
            interp_code = obs.get('interpretation', [{}])[0].get('coding', [{}])[0].get('code', 'N')
            flag = _norm_flag(interp_code)

            if test_name and value:
                results.append(InstrumentResult(
                    test_code     = test_code or test_name[:10].upper(),
                    test_name     = test_name,
                    value         = value,
                    numeric_value = _to_float(value),
                    unit          = unit,
                    reference_min = ref_low,
                    reference_max = ref_high,
                    reference_text= ref_text,
                    flag          = flag,
                    result_source = 'AUTOMATED',
                ))

        return ParseResult(
            ok=True, results=results, format='fhir_r4',
            metadata={'report_id': report.get('id', ''), 'status': report.get('status', '')},
        )
    except Exception as e:
        return ParseResult(ok=False, format='fhir_r4', errors=[str(e)])


# ── Sysmex XN format ─────────────────────────────────────────────────────────

def parse_sysmex_csv(content: str) -> ParseResult:
    """Sysmex XN-series hematology analyzer CSV export."""
    SYSMEX_COLS = {
        'WBC':   ('WBC', 'White Blood Cells', 'x10^3/uL'),
        'RBC':   ('RBC', 'Red Blood Cells',   'x10^6/uL'),
        'HGB':   ('HGB', 'Hemoglobin',         'g/dL'),
        'HCT':   ('HCT', 'Hematocrit',         '%'),
        'MCV':   ('MCV', 'MCV',                'fL'),
        'MCH':   ('MCH', 'MCH',                'pg'),
        'MCHC':  ('MCHC','MCHC',               'g/dL'),
        'PLT':   ('PLT', 'Platelets',          'x10^3/uL'),
        'RDW-CV':('RDW', 'RDW-CV',             '%'),
        'NEUT#': ('NEUT_A','Neutrophils Abs',  'x10^3/uL'),
        'LYMPH#':('LYMPH_A','Lymphocytes Abs', 'x10^3/uL'),
        'MONO#': ('MONO_A','Monocytes Abs',    'x10^3/uL'),
        'EOS#':  ('EOS_A', 'Eosinophils Abs',  'x10^3/uL'),
        'BASO#': ('BASO_A','Basophils Abs',    'x10^3/uL'),
        'NEUT%': ('NEUT_P','Neutrophils %',    '%'),
        'LYMPH%':('LYMPH_P','Lymphocytes %',   '%'),
    }
    # Delegate to generic CSV with Sysmex column mapping
    r = parse_generic_csv(content, instrument_id='SYSMEX_XN')
    r.format = 'sysmex_csv'
    return r


# ── Master parser ─────────────────────────────────────────────────────────────

def parse(
    content:       str,
    filename:      str = '',
    instrument_id: str = '',
    fmt:           str = '',
) -> ParseResult:
    """
    Detect format and parse instrument output.
    Returns ParseResult — never raises.
    """
    content = content.strip()
    if not content:
        return ParseResult(ok=False, errors=['Empty content'])

    # Auto-detect format
    if not fmt:
        if content.startswith('{') and '"resourceType"' in content:
            fmt = 'fhir'
        elif content.startswith('<') and 'GeneXpert' in content:
            fmt = 'genexpert_xml'
        elif content.startswith('<') and 'ASTM' not in content:
            fmt = 'xml'
        elif re.match(r'^H\|', content):
            fmt = 'astm'
        elif 'MSH|' in content[:20]:
            fmt = 'hl7'
        elif '\t' in content[:200] and content.count('\t') > content.count(','):
            fmt = 'tsv'
        else:
            fmt = 'csv'

        # Filename hint
        ext = Path(filename).suffix.lower() if filename else ''
        if ext == '.xml':
            fmt = 'genexpert_xml' if 'GeneXpert' in content else 'xml'
        elif ext in ('.hl7', '.ORU'):
            fmt = 'hl7'

    parsers = {
        'astm':           lambda: parse_astm(content, instrument_id),
        'genexpert_xml':  lambda: parse_genexpert_xml(content),
        'fhir':           lambda: parse_fhir_diagnostic_report(content),
        'hl7':            lambda: _parse_hl7_results(content, instrument_id),
        'sysmex':         lambda: parse_sysmex_csv(content),
        'csv':            lambda: parse_generic_csv(content, instrument_id=instrument_id),
        'tsv':            lambda: parse_generic_csv(content, '\t', instrument_id),
        'xml':            lambda: _parse_generic_xml_results(content),
    }

    parser = parsers.get(fmt, parsers['csv'])
    try:
        result = parser()
        result.format = fmt
        return result
    except Exception as e:
        logger.error('Instrument parser error (%s): %s', fmt, e)
        return ParseResult(ok=False, format=fmt, errors=[str(e)])


async def parse_file(path: str, instrument_id: str = '') -> ParseResult:
    """Parse an instrument output file."""
    try:
        for enc in ('utf-8', 'latin-1', 'cp1252'):
            try:
                content = Path(path).read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return ParseResult(ok=False, errors=['Cannot decode file'])
        return parse(content, filename=path, instrument_id=instrument_id)
    except Exception as e:
        return ParseResult(ok=False, errors=[str(e)])


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_ref_range(ref: str) -> tuple[Optional[float], Optional[float], str]:
    """Parse reference range string: '3.9-6.1' or '3.9 – 6.1' or '<10'."""
    if not ref:
        return None, None, ''
    ref = ref.strip()
    # Range: 3.9-6.1 or 3.9–6.1
    m = re.match(r'([\d.]+)\s*[-–]\s*([\d.]+)', ref)
    if m:
        return float(m.group(1)), float(m.group(2)), ref
    # Less than: <10
    m = re.match(r'<\s*([\d.]+)', ref)
    if m:
        return None, float(m.group(1)), ref
    # Greater than: >10
    m = re.match(r'>\s*([\d.]+)', ref)
    if m:
        return float(m.group(1)), None, ref
    return None, None, ref


def _parse_hl7_results(content: str, instrument_id: str = '') -> ParseResult:
    """Delegate to document_reader HL7 parser then reshape to InstrumentResult."""
    from ai_services.document_reader import _read_hl7
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.hl7', delete=False, encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    try:
        r = _read_hl7(tmp)
        results = []
        if r.ok and r.structured:
            s = r.structured
            results.append(InstrumentResult(
                test_code    = 'HL7_RESULT',
                test_name    = s.get('test_name', 'HL7 Result'),
                value        = s.get('result_value', ''),
                unit         = s.get('result_units', ''),
                reference_text=s.get('ref_range', ''),
                flag         = _norm_flag(s.get('abnormal_flag', 'N')),
                instrument_id= instrument_id,
                patient_id   = s.get('patient_name', ''),
            ))
        return ParseResult(ok=True, results=results, format='hl7', instrument_id=instrument_id)
    finally:
        os.unlink(tmp)


def _parse_generic_xml_results(content: str) -> ParseResult:
    """Parse generic XML result files."""
    results = []
    try:
        root = ET.fromstring(content)
        # Find result-like nodes
        for node in root.iter():
            tag = node.tag.split('}')[-1].lower()
            if 'result' in tag or 'analyte' in tag:
                children = {c.tag.split('}')[-1].lower(): (c.text or '') for c in node}
                value = children.get('value', children.get('result', ''))
                name  = children.get('name', children.get('test', tag))
                if value and name:
                    results.append(InstrumentResult(
                        test_code=name[:10].upper(), test_name=name,
                        value=value, flag='N', raw_line=ET.tostring(node, encoding='unicode')[:200],
                    ))
        return ParseResult(ok=True, results=results, format='xml')
    except Exception as e:
        return ParseResult(ok=False, format='xml', errors=[str(e)])
