"""
Synthetic OCR-noise generator for the OCR-cleanup task.

OCR-cleanup is the step AFTER raw OCR: take noisy text (mis-recognised
characters, broken word boundaries, mixed line breaks) and emit the clean
canonical text. Training pairs are (noisy, clean).

Without real scanned forms we generate the noisy half by applying realistic
OCR-style perturbations to clean lab-request text reconstructed from the
pilot DB (and a few fallback templates so the file is never empty).

Perturbation menu:
  - char swap   o↔0, l↔1, S↔5, B↔8, I↔1, Z↔2  (most common Tesseract drift)
  - case flip   of single letters
  - line break  injection mid-token
  - whitespace  collapse / dup
  - punctuation drop
"""
from __future__ import annotations

import random
from typing import Iterator


_OCR_SUBS = [
    ('O', '0'), ('o', '0'), ('l', '1'), ('I', '1'), ('|', '1'),
    ('S', '5'), ('B', '8'), ('Z', '2'), ('G', '6'), ('q', '9'),
    ('rn', 'm'), ('cl', 'd'),
]

_FALLBACK_FORMS = [
    "PID: PA-001122\nPatient: MUKAMANA Alice\nDOB: 14/03/1992\nSex: F\n"
    "Doctor: Dr Ndayisaba\nWard: Internal Medicine\nDiagnosis: Suspected anemia\n"
    "STAT\nTests requested: CBC, ESR",

    "Patient: HABIMANA Eric\nNID: 1199580012345678\nSex: M\n"
    "Doctor: Dr Uwase\nWard: Surgery\nDiagnosis: Pre-op screen\n"
    "Tests requested: HGB, PLT, PT/INR, APTT",

    "URGENT\nPID: PA-009876\nPatient: KAGABO Patrick\nDOB: 28/11/1985\nSex: M\n"
    "Doctor: Dr Ingabire\nWard: Emergency\nDiagnosis: Septic shock\n"
    "Tests requested: CBC, CRP, lactate, electrolytes",
]


def _noisify(clean: str, rng: random.Random, intensity: float = 0.05) -> str:
    """Apply a small amount of OCR-style noise. `intensity` ≈ fraction of chars affected."""
    out_chars: list[str] = []
    for ch in clean:
        if ch.isalnum() and rng.random() < intensity:
            for src, dst in _OCR_SUBS:
                if ch == src or ch == src[0]:
                    out_chars.append(dst if len(src) == 1 else dst)
                    break
            else:
                out_chars.append(ch.swapcase() if rng.random() < 0.3 else ch)
        else:
            out_chars.append(ch)
    noisy = ''.join(out_chars)

    # Random line-break or whitespace drift
    if rng.random() < 0.3:
        i = rng.randint(0, len(noisy) - 1)
        noisy = noisy[:i] + '\n' + noisy[i:]
    if rng.random() < 0.4:
        noisy = noisy.replace(' ', '  ', 1)
    return noisy


def ocr_pairs(seed_texts: list[str] | None = None, n_per_seed: int = 3) -> Iterator[dict]:
    """
    Yield {noisy, clean, source} dicts.

    `seed_texts` is a list of clean canonical texts (one per real DB row or
    fallback). For each, we emit `n_per_seed` independently noisified copies.
    """
    rng = random.Random(20260522)
    seeds = seed_texts or _FALLBACK_FORMS
    if not seeds:
        seeds = _FALLBACK_FORMS

    for clean in seeds:
        for k in range(n_per_seed):
            yield {
                'noisy':  _noisify(clean, rng, intensity=0.04 + 0.02 * (k / max(n_per_seed - 1, 1))),
                'clean':  clean,
                'source': 'real' if seeds is not _FALLBACK_FORMS else 'fallback',
            }
