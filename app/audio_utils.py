"""
Minimal audio helpers for the pipeline: level (from SDK) and resampling.
Resampling: int16 mono PCM rate_in -> rate_out (e.g. 48k -> 16k for web).
"""

from __future__ import annotations

import logging

from sdk.audio_utils import INT16_MAX, chunk_rms_level

logger = logging.getLogger(__name__)

__all__ = ["chunk_rms_level", "INT16_MAX", "resample_int16"]


def resample_int16(audio_bytes: bytes, rate_in: int, rate_out: int) -> bytes:
    """
    Resample int16 mono PCM from rate_in to rate_out.
    Uses linear interpolation (numpy). Returns bytes of int16 little-endian.
    """
    if rate_in <= 0 or rate_out <= 0:
        return b""
    if rate_in == rate_out:
        return audio_bytes
    n = len(audio_bytes) // 2
    if n == 0:
        return b""
    try:
        import numpy as np
    except ImportError:
        logger.warning("resample_int16 requires numpy")
        return b""
    samples = np.frombuffer(audio_bytes, dtype=np.int16)
    num_out = int(round(n * rate_out / rate_in))
    if num_out == 0:
        return b""
    x_old = np.arange(n, dtype=np.float64)
    x_new = np.linspace(0, n - 1, num_out, dtype=np.float64)
    resampled = np.interp(x_new, x_old, samples.astype(np.float64))
    out = np.clip(resampled, -32768, 32767).astype(np.int16)
    return out.tobytes()
