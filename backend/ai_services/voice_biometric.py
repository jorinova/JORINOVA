"""
JORINOVA NEXUS ALIS-X — Voice Biometric Engine
================================================
Speaker verification using voice embeddings.

Two-tier approach (both fully offline):
  TIER 1 — resemblyzer (preferred): GE2E d-vector, 256-dim
            Very accurate speaker verification (~2% EER)
  TIER 2 — MFCC (fallback): 39-dim feature vector via librosa
            Works without deep learning, sufficient for controlled environments

Verification flow:
  1. User speaks a phrase (recorded in browser via MediaRecorder)
  2. Audio blob → extract embedding
  3. Cosine similarity against stored enrollment embedding
  4. PASS if similarity ≥ threshold (default 0.75)
  5. Result + similarity score → audit log

Security thresholds (tuned for hospital lab):
  0.90+ → Very high confidence (biometric match)
  0.75–0.89 → Sufficient for voice commands
  0.60–0.74 → Low confidence — prompt to repeat
  < 0.60  → Reject — different speaker or poor audio

BLOCKED roles: intern, visitor, student, guest, observer
"""
from __future__ import annotations
import io
import json
import logging
import math
import time
from typing import Optional

import numpy as np

logger = logging.getLogger('voice_biometric')


# ── Embedding extraction ──────────────────────────────────────────────────────

def extract_embedding(audio_bytes: bytes, sample_rate: int = 16000,
                      method: str = 'auto') -> tuple[np.ndarray, str]:
    """
    Extract a speaker embedding from raw audio bytes (WAV/WebM/OGG).
    Returns (embedding_vector, method_used).
    """
    # Decode audio to waveform
    waveform = _decode_audio(audio_bytes, sample_rate)
    if waveform is None or len(waveform) < sample_rate * 0.5:
        raise ValueError('Audio too short or unreadable (minimum 0.5 seconds required)')

    if method in ('resemblyzer', 'auto'):
        emb, met = _extract_resemblyzer(waveform, sample_rate)
        if emb is not None:
            return emb, met

    # Fallback: MFCC
    emb, met = _extract_mfcc(waveform, sample_rate)
    if emb is not None:
        return emb, met

    raise RuntimeError('No audio feature extraction method available. '
                       'Install: pip install resemblyzer librosa')


def _decode_audio(audio_bytes: bytes, target_sr: int = 16000) -> Optional[np.ndarray]:
    """Decode audio bytes (WebM/OGG/WAV) to float32 numpy array."""
    try:
        import soundfile as sf
        buf = io.BytesIO(audio_bytes)
        waveform, sr = sf.read(buf, dtype='float32')
        if waveform.ndim > 1:
            waveform = waveform.mean(axis=1)  # stereo → mono
        if sr != target_sr:
            waveform = _resample(waveform, sr, target_sr)
        return waveform
    except Exception as e:
        logger.debug('soundfile decode failed: %s', e)

    # Fallback: try scipy
    try:
        from scipy.io import wavfile
        import tempfile, subprocess
        # Convert WebM/OGG to WAV using ffmpeg if available
        with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
            try:
                subprocess.run(['ffmpeg', '-i', '-', '-ar', str(target_sr),
                                '-ac', '1', '-f', 'wav', tmp.name],
                               input=audio_bytes, capture_output=True, timeout=10)
                sr, data = wavfile.read(tmp.name)
                return data.astype(np.float32) / 32768.0
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        sr, data = wavfile.read(io.BytesIO(audio_bytes))
        arr = data.astype(np.float32)
        if arr.max() > 1.0:
            arr /= 32768.0
        return arr
    except Exception as e:
        logger.debug('scipy decode failed: %s', e)

    logger.error('Could not decode audio. Install soundfile: pip install soundfile')
    return None


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Simple linear resampling."""
    try:
        import librosa
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
    except ImportError:
        # Manual resampling
        ratio = target_sr / orig_sr
        new_len = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, new_len)
        return np.interp(indices, np.arange(len(audio)), audio)


def _extract_resemblyzer(waveform: np.ndarray, sr: int) -> tuple[Optional[np.ndarray], str]:
    """Extract 256-dim d-vector using resemblyzer."""
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
        wav = preprocess_wav(waveform, source_sr=sr)
        encoder = _get_encoder()
        embedding = encoder.embed_utterance(wav)
        return embedding.astype(np.float32), 'resemblyzer'
    except ImportError:
        return None, 'resemblyzer_unavailable'
    except Exception as e:
        logger.warning('resemblyzer failed: %s', e)
        return None, 'resemblyzer_error'


_encoder_cache = None

def _get_encoder():
    """Cache the voice encoder (loading takes ~1s)."""
    global _encoder_cache
    if _encoder_cache is None:
        from resemblyzer import VoiceEncoder
        _encoder_cache = VoiceEncoder()
        logger.info('Voice encoder loaded (resemblyzer)')
    return _encoder_cache


def _extract_mfcc(waveform: np.ndarray, sr: int) -> tuple[Optional[np.ndarray], str]:
    """
    Extract 39-dim MFCC+delta+delta2 feature vector.
    Averaged over time → single speaker embedding.
    Works offline without deep learning.
    """
    try:
        import librosa
        # MFCC: 13 coefficients × 3 (static + delta + delta2) = 39 dims
        mfcc = librosa.feature.mfcc(y=waveform, sr=sr, n_mfcc=13)
        d1   = librosa.feature.delta(mfcc)
        d2   = librosa.feature.delta(mfcc, order=2)
        feat = np.vstack([mfcc, d1, d2])       # (39, T)
        emb  = feat.mean(axis=1).astype(np.float32)  # (39,)
        return emb, 'mfcc'
    except ImportError:
        pass

    # Ultra-fallback: ZCR + spectral centroid (no librosa)
    try:
        # Zero-crossing rate
        zcr = np.mean(np.abs(np.diff(np.sign(waveform))))
        # RMS energy
        rms = np.sqrt(np.mean(waveform ** 2))
        # Fundamental frequency estimate (autocorrelation peak)
        acf = np.correlate(waveform[:1024], waveform[:1024], mode='full')
        acf = acf[len(acf)//2:]
        f0_idx = np.argmax(acf[20:]) + 20
        f0 = sr / f0_idx if f0_idx > 0 else 0
        emb = np.array([zcr, rms, f0 / 1000.0], dtype=np.float32)
        return emb, 'basic_features'
    except Exception as e:
        logger.error('All feature extraction failed: %s', e)
        return None, 'failed'


# ── Similarity computation ────────────────────────────────────────────────────

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two embedding vectors.
    Returns 0–1 (1.0 = identical speaker).
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def verify_speaker(
    audio_bytes: bytes,
    stored_embedding_json: str,
    threshold: float = 0.75,
    sample_rate: int = 16000,
) -> dict:
    """
    Verify that the audio belongs to the enrolled speaker.

    Args:
        audio_bytes:          Raw audio from browser (WebM/OGG/WAV)
        stored_embedding_json: JSON string with stored embedding(s)
        threshold:            Minimum similarity to accept (0.75 default)
        sample_rate:          Target sample rate

    Returns:
        {
            'passed': bool,
            'similarity': float (0–1),
            'threshold': float,
            'method': str,
            'duration_s': float,
            'message': str,
        }
    """
    start = time.time()
    result = {
        'passed': False, 'similarity': 0.0,
        'threshold': threshold, 'method': 'unknown',
        'duration_s': 0.0, 'message': '',
    }

    try:
        # Extract embedding from incoming audio
        new_emb, method = extract_embedding(audio_bytes, sample_rate)
        result['method'] = method

        # Load stored embedding(s)
        stored = json.loads(stored_embedding_json)
        if isinstance(stored[0], list):
            # Multiple samples → compare against each, take max
            stored_embs = [np.array(e, dtype=np.float32) for e in stored]
        else:
            stored_embs = [np.array(stored, dtype=np.float32)]

        # Compute similarities against all stored embeddings
        similarities = [cosine_similarity(new_emb, se) for se in stored_embs]
        best_sim = max(similarities)
        mean_sim = sum(similarities) / len(similarities)

        # Use best match (most favourable for user)
        sim = best_sim
        result['similarity'] = round(float(sim), 4)

        if sim >= threshold:
            result['passed'] = True
            result['message'] = (
                f'Voice verified ✓ (similarity: {sim:.1%}, '
                f'threshold: {threshold:.0%})'
            )
            logger.info('Voice verification PASSED: sim=%.3f threshold=%.2f', sim, threshold)
        else:
            result['passed'] = False
            if sim >= 0.60:
                result['message'] = (
                    f'Voice similarity too low ({sim:.1%} < {threshold:.0%}). '
                    'Please speak clearly and try again.'
                )
            else:
                result['message'] = (
                    f'Voice not recognised ({sim:.1%}). '
                    'This voice does not match the registered voiceprint for this account.'
                )
            logger.warning('Voice verification FAILED: sim=%.3f threshold=%.2f', sim, threshold)

    except ValueError as e:
        result['message'] = str(e)
        result['failure_reason'] = 'AUDIO_ERROR'
        logger.warning('Voice verification audio error: %s', e)
    except Exception as e:
        result['message'] = f'Verification error: {e}'
        result['failure_reason'] = 'SYSTEM_ERROR'
        logger.error('Voice verification error: %s', e)
    finally:
        result['duration_s'] = round(time.time() - start, 3)

    return result


def compute_enrollment_quality(embeddings: list[np.ndarray]) -> float:
    """
    Compute intra-speaker similarity — how consistent the recordings are.
    High quality = recordings sound similar (same person, same conditions).
    Returns 0–1 quality score.
    """
    if len(embeddings) < 2:
        return 0.0
    sims = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            sims.append(cosine_similarity(embeddings[i], embeddings[j]))
    return round(float(sum(sims) / len(sims)), 4)


def average_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    """Average multiple embeddings into one representative voiceprint."""
    if not embeddings:
        raise ValueError('No embeddings to average')
    stacked = np.stack(embeddings, axis=0)
    avg = stacked.mean(axis=0)
    # L2-normalise for consistent cosine similarity
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg.astype(np.float32)


# ── Role access control ───────────────────────────────────────────────────────

def check_voice_access(role: str) -> dict:
    """
    Check if a user's role allows voice command access.
    Interns, visitors, observers are BLOCKED by design.
    """
    from models.voice_biometric import VOICE_ALLOWED_ROLES, VOICE_BLOCKED_ROLES

    if role in VOICE_BLOCKED_ROLES:
        return {
            'allowed': False,
            'reason': 'BLOCKED_ROLE',
            'message': (
                f'Voice access is not available for role: {role}. '
                'Interns, visitors, and observers must use keyboard login only. '
                'Voice biometrics require an enrolled staff account.'
            ),
        }

    if role not in VOICE_ALLOWED_ROLES:
        return {
            'allowed': False,
            'reason': 'UNKNOWN_ROLE',
            'message': f'Role "{role}" is not configured for voice access. Contact your lab manager.',
        }

    return {
        'allowed': True,
        'reason': None,
        'message': f'Voice access permitted for role: {role}',
    }


# ── Training phrases ──────────────────────────────────────────────────────────

# Phonetically diverse phrases for enrollment (cover broad phoneme range)
ENROLLMENT_PHRASES = [
    "My name is registered in JORINOVA NEXUS laboratory system",
    "I am an authorized laboratory staff member at this hospital",
    "ALIS-X voice authentication — please verify my identity",
    "The blood sample belongs to the patient with ID number one two three",
    "Quality control passed — result is validated and released",
    "Critical value detected — notifying the clinician immediately",
    "Good morning, this is the morning shift handover for haematology",
]

def get_enrollment_phrases(count: int = 5) -> list[str]:
    """Return `count` randomly selected enrollment phrases."""
    import random
    return random.sample(ENROLLMENT_PHRASES, min(count, len(ENROLLMENT_PHRASES)))
