"""
ALIS-X OCR Service
==================
Multilingual optical character recognition pipeline.

Priority chain (offline-first):
  1. Tesseract (offline, multilingual, CPU-only) — best for printed text
  2. EasyOCR  (offline, deep-learning, CPU)     — best for handwriting/poor quality
  3. Claude Vision (cloud)                       — best for complex layouts
  4. PIL + text extraction                        — absolute fallback

Supports:
  - Printed lab reports
  - Handwritten notes
  - Scanned supplier invoices
  - Sample tube labels (combined with barcode_service)
  - Microscope image overlays
  - Medical form fields
  - Multilingual documents (en / fr / rw + 100+ via Tesseract)
"""
from __future__ import annotations

import io
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ai_services.language_service import get_tesseract_lang

logger = logging.getLogger('ocr_service')


@dataclass
class OCRResult:
    ok:          bool
    text:        str         = ''
    words:       list[dict]  = field(default_factory=list)  # [{word, confidence, bbox}]
    blocks:      list[dict]  = field(default_factory=list)  # paragraph blocks
    tables:      list[list]  = field(default_factory=list)  # extracted table cells
    lang:        str         = 'en'
    engine:      str         = ''
    confidence:  float       = 0.0
    latency_ms:  int         = 0
    warnings:    list[str]   = field(default_factory=list)
    error:       str         = ''

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ── Image preprocessing ───────────────────────────────────────────────────────

def preprocess_image(image_path: str, enhance: bool = True) -> Optional[object]:
    """
    Preprocess image for better OCR accuracy.
    Applies: grayscale, contrast enhancement, denoising, thresholding.
    Returns PIL Image or None.
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        img = Image.open(image_path)

        # Convert to RGB if needed
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        if not enhance:
            return img

        # Convert to grayscale for OCR
        img = img.convert('L')

        # Enhance contrast
        img = ImageEnhance.Contrast(img).enhance(2.0)

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        # Auto-rotate based on EXIF
        img = ImageOps.exif_transpose(img)

        return img
    except ImportError:
        logger.debug('PIL not installed for preprocessing')
        return None
    except Exception as e:
        logger.warning('Image preprocessing failed: %s', e)
        return None


# ── Tesseract OCR ─────────────────────────────────────────────────────────────

def ocr_tesseract(
    image_path:  str,
    lang:        str = 'en',
    psm:         int = 3,     # page segmentation mode (3=auto, 6=uniform block, 11=sparse)
    enhance:     bool = True,
) -> OCRResult:
    """
    Tesseract OCR — offline, multilingual.
    psm values:
      3  = Fully automatic page segmentation (default)
      6  = Assume a single uniform block of text
      11 = Sparse text (for labels, receipts)
      12 = Sparse text with OSD
    """
    t0 = time.time()
    tess_lang = get_tesseract_lang(lang)

    try:
        import pytesseract
        from PIL import Image

        img = preprocess_image(image_path, enhance) or Image.open(image_path)

        # Full OCR with detailed output
        config = f'--psm {psm} --oem 1'  # oem 1 = LSTM
        text   = pytesseract.image_to_string(img, lang=tess_lang, config=config)

        # Confidence data
        data = pytesseract.image_to_data(img, lang=tess_lang, config=config,
                                          output_type=pytesseract.Output.DICT)
        words = []
        total_conf, conf_count = 0.0, 0
        for i, word in enumerate(data['text']):
            conf = int(data['conf'][i])
            if word.strip() and conf > 0:
                words.append({
                    'word':       word.strip(),
                    'confidence': conf / 100.0,
                    'left':  data['left'][i],
                    'top':   data['top'][i],
                    'width': data['width'][i],
                    'height':data['height'][i],
                })
                total_conf  += conf
                conf_count  += 1

        avg_confidence = (total_conf / conf_count / 100.0) if conf_count else 0.0

        return OCRResult(
            ok=True, text=text.strip(), words=words, lang=lang,
            engine='tesseract', confidence=round(avg_confidence, 3),
            latency_ms=int((time.time()-t0)*1000),
        )

    except ImportError:
        return OCRResult(ok=False, engine='tesseract',
                         error='pytesseract not installed (pip install pytesseract)',
                         warnings=['Also requires Tesseract binary: https://github.com/UB-Mannheim/tesseract/wiki'],
                         latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return OCRResult(ok=False, engine='tesseract', error=str(e),
                         latency_ms=int((time.time()-t0)*1000))


# ── EasyOCR ───────────────────────────────────────────────────────────────────

def ocr_easyocr(
    image_path: str,
    lang:       str = 'en',
) -> OCRResult:
    """
    EasyOCR — offline deep-learning OCR.
    Better than Tesseract for handwriting and poor-quality images.
    First run downloads models (~100MB) — subsequent runs are offline.
    """
    t0 = time.time()
    try:
        import easyocr
        lang_list = [lang, 'en'] if lang != 'en' else ['en']
        reader    = easyocr.Reader(lang_list, gpu=False, verbose=False)
        results   = reader.readtext(image_path, detail=1)

        words = []
        full_text_parts = []
        confidences = []

        for (bbox, text, conf) in results:
            if text.strip():
                words.append({
                    'word':       text.strip(),
                    'confidence': round(conf, 3),
                    'bbox':       bbox,
                })
                full_text_parts.append(text.strip())
                confidences.append(conf)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        full_text = ' '.join(full_text_parts)

        return OCRResult(
            ok=True, text=full_text, words=words, lang=lang,
            engine='easyocr', confidence=round(avg_conf, 3),
            latency_ms=int((time.time()-t0)*1000),
        )
    except ImportError:
        return OCRResult(ok=False, engine='easyocr',
                         error='easyocr not installed (pip install easyocr)',
                         latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return OCRResult(ok=False, engine='easyocr', error=str(e),
                         latency_ms=int((time.time()-t0)*1000))


# ── Claude Vision OCR ─────────────────────────────────────────────────────────

async def ocr_claude_vision(
    image_path: str,
    lang:       str = 'en',
    task:       str = 'general',   # general|lab_report|invoice|form
) -> OCRResult:
    """
    Claude Vision OCR — cloud-only, highest accuracy.
    Understands context (lab results, tables, handwriting).
    NEVER call this with patient-identifiable data unless cloud_ok=True.
    """
    t0 = time.time()
    try:
        from ai_services.cloud_llm import is_available
        if not await is_available():
            return OCRResult(ok=False, engine='claude_vision',
                             error='Cloud not available',
                             latency_ms=int((time.time()-t0)*1000))

        import base64, anthropic
        from core.config import get_settings
        s = get_settings()

        with open(image_path, 'rb') as f:
            img_b64 = base64.standard_b64encode(f.read()).decode()

        suffix_mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                       '.png': 'image/png', '.webp': 'image/webp',
                       '.bmp': 'image/jpeg', '.tiff': 'image/tiff'}
        mime = suffix_mime.get(Path(image_path).suffix.lower(), 'image/jpeg')

        task_prompts = {
            'lab_report': (
                'This is a laboratory report or result document. '
                'Extract ALL text exactly as written, preserving the table structure. '
                'Then extract key-value pairs: test names, values, units, reference ranges, flags, dates. '
            ),
            'invoice': (
                'This is a supplier invoice or purchase order. '
                'Extract all text and identify: supplier name, date, item names, quantities, unit prices, totals. '
            ),
            'form': (
                'This is a medical form. '
                'Extract all field labels and their values. Preserve the form structure. '
            ),
            'general': 'Extract all text exactly as it appears. ',
        }

        prompt = (
            f'{task_prompts.get(task, task_prompts["general"])}'
            f'The document is in {lang}. '
            f'Respond in JSON: {{"full_text":"...","extracted_data":{{"key":"value"}},'
            f'"tables":[[]],"confidence":"high|medium|low"}}'
        )

        client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
        msg = await client.messages.create(
            model=s.claude_model, max_tokens=1500,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': img_b64}},
                    {'type': 'text', 'text': prompt},
                ],
            }],
        )
        raw = msg.content[0].text.strip() if msg.content else ''

        import json
        text = raw
        data = {}
        if '```json' in text:
            text = text.split('```json', 1)[1].rsplit('```', 1)[0]
        try:
            data = json.loads(text.strip())
        except Exception:
            data = {'full_text': raw}

        full_text = data.get('full_text', raw)
        confidence = {'high': 0.9, 'medium': 0.7, 'low': 0.4}.get(data.get('confidence', 'medium'), 0.7)

        return OCRResult(
            ok=True, text=full_text, lang=lang,
            engine='claude_vision', confidence=confidence,
            blocks=data.get('extracted_data', {}),
            tables=data.get('tables', []),
            latency_ms=int((time.time()-t0)*1000),
        )

    except Exception as e:
        return OCRResult(ok=False, engine='claude_vision', error=str(e),
                         latency_ms=int((time.time()-t0)*1000))


# ── Master OCR pipeline ───────────────────────────────────────────────────────

async def ocr(
    image_path:  str,
    lang:        str   = 'en',
    task:        str   = 'general',
    cloud_ok:    bool  = False,
    enhance:     bool  = True,
) -> OCRResult:
    """
    Master OCR — tries engines in order, returns best result.
    Never raises — errors in OCRResult.error.
    """
    # 1. Tesseract (offline preferred)
    result = ocr_tesseract(image_path, lang, enhance=enhance)
    if result.ok and result.confidence > 0.4 and len(result.text) > 10:
        logger.info('OCR by Tesseract: conf=%.2f words=%d', result.confidence, len(result.words))
        return result

    # 2. EasyOCR (offline, better for degraded images)
    result2 = ocr_easyocr(image_path, lang)
    if result2.ok and result2.confidence > 0.3 and len(result2.text) > 10:
        logger.info('OCR by EasyOCR: conf=%.2f', result2.confidence)
        return result2

    # 3. Claude Vision (cloud, best accuracy)
    if cloud_ok:
        result3 = await ocr_claude_vision(image_path, lang, task)
        if result3.ok and result3.text:
            logger.info('OCR by Claude Vision: conf=%.2f', result3.confidence)
            return result3

    # 4. Return best partial result
    best = result if result.ok else (result2 if result2.ok else result)
    if not best.ok:
        best.warnings.append('All OCR engines failed. Check installations.')
    return best


# ── PDF page OCR ──────────────────────────────────────────────────────────────

async def ocr_pdf(
    pdf_path:  str,
    lang:      str  = 'en',
    cloud_ok:  bool = False,
    max_pages: int  = 20,
) -> OCRResult:
    """
    OCR all pages of a scanned PDF.
    Converts each page to an image, then runs OCR.
    """
    t0 = time.time()
    try:
        # Try pdf2image for conversion
        from pdf2image import convert_from_path
        import tempfile, asyncio

        images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=max_pages)
        pages_text = []

        for i, img in enumerate(images):
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name)
                tmp = f.name
            try:
                page_result = await ocr(tmp, lang, cloud_ok=cloud_ok)
                pages_text.append(page_result.text)
            finally:
                Path(tmp).unlink(missing_ok=True)

        return OCRResult(
            ok=True, text='\n\n'.join(pages_text), engine='tesseract_pdf',
            lang=lang, latency_ms=int((time.time()-t0)*1000),
            warnings=[f'{len(images)} pages processed'],
        )

    except ImportError:
        return OCRResult(ok=False, error='pdf2image not installed (pip install pdf2image). Also requires poppler.',
                         latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return OCRResult(ok=False, error=f'PDF OCR failed: {e}',
                         latency_ms=int((time.time()-t0)*1000))


# ── Lab report OCR + structured extraction ────────────────────────────────────

async def extract_lab_results_from_image(
    image_path: str,
    lang:       str  = 'en',
    cloud_ok:   bool = False,
) -> dict:
    """
    High-level function: OCR a lab report image → extract structured results.
    Returns list of {test_name, value, unit, reference_range, flag}.
    """
    ocr_result = await ocr(image_path, lang, task='lab_report', cloud_ok=cloud_ok)

    if not ocr_result.ok or not ocr_result.text:
        return {'ok': False, 'error': ocr_result.error, 'results': []}

    # Pattern-based extraction for common lab result formats
    results = _extract_lab_patterns(ocr_result.text)

    # AI enhancement if local LLM available
    if not results or len(results) < 2:
        try:
            from ai_services.local_llm import generate, is_available
            if await is_available():
                prompt = (
                    f'Extract laboratory test results from this OCR text:\n\n'
                    f'{ocr_result.text[:2000]}\n\n'
                    f'Respond ONLY in JSON: {{"results":[{{"test_name":"...","value":"...","unit":"...","reference_range":"...","flag":"N|H|L|HH|LL|POS|NEG"}}]}}'
                )
                resp = await generate(prompt, max_tokens=600, timeout_s=12.0)
                if resp.content:
                    import json
                    text = resp.content
                    if '```json' in text:
                        text = text.split('```json', 1)[1].rsplit('```', 1)[0]
                    data = json.loads(text.strip())
                    results = data.get('results', results)
        except Exception as e:
            logger.debug('AI lab extraction failed: %s', e)

    return {
        'ok':       True,
        'results':  results,
        'raw_text': ocr_result.text,
        'engine':   ocr_result.engine,
        'confidence': ocr_result.confidence,
    }


def _extract_lab_patterns(text: str) -> list[dict]:
    """
    Regex-based lab result extraction.
    Handles common formats: 'Glucose: 5.4 mmol/L (3.9-6.1) N'
    """
    results = []
    patterns = [
        # Format: TestName: Value Unit (Ref) Flag
        re.compile(
            r'([A-Za-z][A-Za-z\s\-/]+?)\s*:?\s+'      # test name
            r'([\d.,<>]+)\s*'                           # value
            r'([a-zA-Z/%µ\^²³]+(?:/[a-zA-Z]+)?)?\s*'  # unit (optional)
            r'(?:\(?([\d.,<>]+\s*[-–]\s*[\d.,<>]+)\)?)?'  # ref range (optional)
            r'\s*(H{1,2}|L{1,2}|N|POS|NEG|High|Low|Normal|Positive|Negative)?',
            re.IGNORECASE,
        ),
        # Format: TestName Value Unit
        re.compile(
            r'^([A-Za-z][A-Za-z\s\-]+?)\s+([\d.,]+)\s+([a-zA-Z/%µ]+(?:/[a-zA-Z]+)?)',
            re.MULTILINE,
        ),
    ]
    seen = set()
    for pattern in patterns:
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            val  = m.group(2).strip() if m.lastindex >= 2 else ''
            unit = (m.group(3) or '').strip() if m.lastindex >= 3 else ''
            ref  = (m.group(4) or '').strip() if m.lastindex >= 4 else ''
            flag = (m.group(5) or 'N').strip().upper() if m.lastindex >= 5 else 'N'

            if len(name) < 2 or len(name) > 60:
                continue
            if not val or not re.search(r'\d', val):
                continue

            key = f'{name.lower()}:{val}'
            if key in seen:
                continue
            seen.add(key)

            # Normalise flag
            flag_map = {'HIGH': 'H', 'LOW': 'L', 'POSITIVE': 'POS',
                        'NEGATIVE': 'NEG', 'NORMAL': 'N', 'HH': 'HH', 'LL': 'LL'}
            flag = flag_map.get(flag, flag or 'N')

            results.append({
                'test_name':       name,
                'value':           val,
                'unit':            unit,
                'reference_range': ref,
                'flag':            flag,
            })

    return results[:50]  # cap at 50 results


# ── Health check ──────────────────────────────────────────────────────────────

def health_status() -> dict:
    engines = {}
    for engine, pkg in [('tesseract', 'pytesseract'), ('easyocr', 'easyocr'),
                         ('pdf2image', 'pdf2image'), ('pil', 'PIL')]:
        try:
            __import__(pkg)
            engines[engine] = True
        except ImportError:
            engines[engine] = False
    return {
        'engines':       engines,
        'offline_capable': engines.get('tesseract') or engines.get('easyocr'),
        'pdf_support':   engines.get('pdf2image'),
        'cloud_fallback':'available when Anthropic API configured',
    }
