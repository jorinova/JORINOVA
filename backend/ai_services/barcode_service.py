"""
ALIS-X Barcode & QR Code Service
==================================
Decodes barcodes and QR codes from sample tube labels,
specimen containers, blood bags, and supplier packages.

Priority chain (offline-first):
  1. pyzbar  (offline, fast, 1D + QR)
  2. OpenCV  (offline, QR only)
  3. PIL     (offline, QR only via pyzbar)
  4. Claude Vision (cloud, handles damaged/partial codes)

Lab use cases:
  - Sample tube SID (specimen ID) scanning
  - LID (Lab ID) QR codes
  - Blood bag unit IDs
  - Supplier package barcodes (EAN-13, Code-128)
  - Instrument QC material lot numbers
  - Medication barcodes (GS1-128)

Supported barcode types:
  QR Code, Code-128, Code-39, EAN-13, EAN-8,
  UPC-A, UPC-E, DataMatrix, PDF417, ITF, Codabar
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger('barcode_service')


@dataclass
class BarcodeResult:
    ok:        bool
    codes:     list[dict] = field(default_factory=list)
    # Each code: {data, type, rect, confidence}
    raw_image: Optional[str] = None
    engine:    str = ''
    latency_ms:int = 0
    error:     str = ''
    warnings:  list[str] = field(default_factory=list)

    @property
    def primary(self) -> Optional[str]:
        """Return the first decoded barcode string."""
        return self.codes[0]['data'] if self.codes else None

    @property
    def all_codes(self) -> list[str]:
        return [c['data'] for c in self.codes]


# ── pyzbar decoder ────────────────────────────────────────────────────────────

def decode_pyzbar(image_path: str) -> BarcodeResult:
    """
    pyzbar — fast offline decoder for 1D and 2D barcodes.
    Requires: pip install pyzbar + zbar system library.
    """
    t0 = time.time()
    try:
        from pyzbar import pyzbar
        from PIL import Image

        img    = Image.open(image_path)
        # Try multiple image modes for robustness
        for mode in [img, img.convert('L'), img.convert('RGB')]:
            decoded = pyzbar.decode(mode)
            if decoded:
                codes = []
                for d in decoded:
                    codes.append({
                        'data':       d.data.decode('utf-8', errors='replace'),
                        'type':       d.type,
                        'rect':       {'left': d.rect.left, 'top': d.rect.top,
                                       'width': d.rect.width, 'height': d.rect.height},
                        'confidence': 1.0,  # pyzbar is deterministic
                    })
                return BarcodeResult(ok=True, codes=codes, engine='pyzbar',
                                     latency_ms=int((time.time()-t0)*1000))

        return BarcodeResult(ok=True, codes=[], engine='pyzbar',
                             warnings=['No barcodes detected'],
                             latency_ms=int((time.time()-t0)*1000))

    except ImportError:
        return BarcodeResult(ok=False, engine='pyzbar',
                             error='pyzbar not installed (pip install pyzbar)',
                             warnings=['Also requires zbar library on the system'],
                             latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return BarcodeResult(ok=False, engine='pyzbar', error=str(e),
                             latency_ms=int((time.time()-t0)*1000))


# ── OpenCV QR detector ────────────────────────────────────────────────────────

def decode_opencv(image_path: str) -> BarcodeResult:
    """OpenCV QR Code detector (offline, QR only)."""
    t0 = time.time()
    try:
        import cv2
        img     = cv2.imread(image_path)
        detector = cv2.QRCodeDetector()
        data, pts, _ = detector.detectAndDecode(img)
        if data:
            return BarcodeResult(
                ok=True, engine='opencv',
                codes=[{'data': data, 'type': 'QRCODE', 'confidence': 0.95}],
                latency_ms=int((time.time()-t0)*1000),
            )
        # Try WeChatQR for better accuracy
        try:
            detector2 = cv2.wechat_qrcode_WeChatQRCode()
            texts, _  = detector2.detectAndDecode(img)
            if texts:
                codes = [{'data': t, 'type': 'QRCODE', 'confidence': 0.9} for t in texts]
                return BarcodeResult(ok=True, codes=codes, engine='opencv_wechat',
                                     latency_ms=int((time.time()-t0)*1000))
        except Exception:
            pass
        return BarcodeResult(ok=True, codes=[], engine='opencv',
                             warnings=['No QR code detected'],
                             latency_ms=int((time.time()-t0)*1000))

    except ImportError:
        return BarcodeResult(ok=False, engine='opencv',
                             error='cv2 not installed (pip install opencv-python)',
                             latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return BarcodeResult(ok=False, engine='opencv', error=str(e),
                             latency_ms=int((time.time()-t0)*1000))


# ── Zxing (pure Python fallback) ─────────────────────────────────────────────

def decode_zxing(image_path: str) -> BarcodeResult:
    """python-zxing — Java-based decoder (offline, comprehensive format support)."""
    t0 = time.time()
    try:
        import zxing
        reader = zxing.BarCodeReader()
        code   = reader.decode(image_path)
        if code and code.parsed:
            return BarcodeResult(
                ok=True, engine='zxing',
                codes=[{'data': code.parsed, 'type': code.format, 'confidence': 0.9}],
                latency_ms=int((time.time()-t0)*1000),
            )
        return BarcodeResult(ok=True, codes=[], engine='zxing',
                             warnings=['No barcode detected'],
                             latency_ms=int((time.time()-t0)*1000))
    except ImportError:
        return BarcodeResult(ok=False, engine='zxing',
                             error='zxing not installed (pip install zxing)',
                             latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        return BarcodeResult(ok=False, engine='zxing', error=str(e),
                             latency_ms=int((time.time()-t0)*1000))


# ── Claude Vision barcode fallback ────────────────────────────────────────────

async def decode_cloud_vision(image_path: str) -> BarcodeResult:
    """
    Use Claude Vision to read barcodes from images when offline decoders fail.
    Best for: damaged labels, low-contrast barcodes, partial codes.
    """
    t0 = time.time()
    try:
        from ai_services.cloud_llm import is_available
        if not await is_available():
            return BarcodeResult(ok=False, engine='cloud_vision',
                                 error='Cloud not available',
                                 latency_ms=int((time.time()-t0)*1000))

        import base64, anthropic
        from core.config import get_settings
        s = get_settings()

        with open(image_path, 'rb') as f:
            img_b64 = base64.standard_b64encode(f.read()).decode()

        suffix_mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                       '.png': 'image/png', '.webp': 'image/webp'}
        mime = suffix_mime.get(Path(image_path).suffix.lower(), 'image/jpeg')

        client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
        msg = await client.messages.create(
            model=s.claude_model, max_tokens=300,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': img_b64}},
                    {'type': 'text', 'text': 'Read any barcodes or QR codes in this image. '
                     'Return ONLY the decoded text, one per line. '
                     'If no barcode visible, return "NONE".'},
                ],
            }],
        )
        raw = (msg.content[0].text or '').strip()
        if raw == 'NONE' or not raw:
            return BarcodeResult(ok=True, codes=[], engine='claude_vision',
                                 latency_ms=int((time.time()-t0)*1000))

        codes = [{'data': line.strip(), 'type': 'UNKNOWN', 'confidence': 0.7}
                 for line in raw.split('\n') if line.strip()]
        return BarcodeResult(ok=True, codes=codes, engine='claude_vision',
                             latency_ms=int((time.time()-t0)*1000))

    except Exception as e:
        return BarcodeResult(ok=False, engine='claude_vision', error=str(e),
                             latency_ms=int((time.time()-t0)*1000))


# ── Master decoder ────────────────────────────────────────────────────────────

async def decode(
    image_path: str,
    cloud_ok:   bool = False,
) -> BarcodeResult:
    """
    Master barcode decoder — tries engines in order.
    Returns first successful decode with codes.
    """
    # 1. pyzbar (fastest, most formats)
    r = decode_pyzbar(image_path)
    if r.ok and r.codes:
        return r

    # 2. OpenCV (QR specific)
    r2 = decode_opencv(image_path)
    if r2.ok and r2.codes:
        return r2

    # 3. Zxing (comprehensive format support)
    r3 = decode_zxing(image_path)
    if r3.ok and r3.codes:
        return r3

    # 4. Cloud vision fallback
    if cloud_ok:
        r4 = await decode_cloud_vision(image_path)
        if r4.ok and r4.codes:
            return r4

    # No codes found — return best result
    if r.ok:
        return r
    return BarcodeResult(ok=False, codes=[],
                         error='All decoders failed. Check image quality.',
                         warnings=[r.error, r2.error if not r2.ok else ''])


async def decode_bytes(
    content:   bytes,
    filename:  str = 'barcode.jpg',
    cloud_ok:  bool = False,
) -> BarcodeResult:
    """Decode from bytes."""
    import tempfile
    suffix = Path(filename).suffix or '.jpg'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        return await decode(tmp, cloud_ok)
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── SID / LID parser ──────────────────────────────────────────────────────────

def parse_lab_code(barcode_data: str) -> dict:
    """
    Parse a decoded barcode string into lab identifiers.
    Handles: SID-XXXX, RW-XXXXXXX, LAB-YYYY-XXXXX, PID-XXXX patterns.
    """
    data = barcode_data.strip()
    import re
    patterns = {
        'SID':        re.compile(r'^SID-[\dA-Z][\dA-Z\-]*$', re.I),
        'LID':        re.compile(r'^RW-\d+$', re.I),
        'LAB_REQ':    re.compile(r'^LAB-\d{4}-\d+$', re.I),
        'PID':        re.compile(r'^PID-\d{4}-\d+$', re.I),
        'BLOOD_UNIT': re.compile(r'^BLD-[\dA-Z][\dA-Z\-]*$', re.I),
        'EAN13':      re.compile(r'^\d{13}$'),
        'EAN8':       re.compile(r'^\d{8}$'),
        'CODE128':    re.compile(r'^[A-Z0-9\-. ]+$', re.I),
    }
    for code_type, pattern in patterns.items():
        if pattern.match(data):
            return {'type': code_type, 'value': data, 'parsed': True}
    return {'type': 'UNKNOWN', 'value': data, 'parsed': False}


def health_status() -> dict:
    status = {}
    for lib, pkg in [('pyzbar', 'pyzbar'), ('opencv', 'cv2'), ('zxing', 'zxing'), ('PIL', 'PIL')]:
        try:
            __import__(pkg)
            status[lib] = True
        except ImportError:
            status[lib] = False
    return {
        'decoders':       status,
        'offline_capable': any(status.values()),
        'recommended':    'pip install pyzbar pillow',
    }
