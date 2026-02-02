"""
Shared audio utilities: RMS level from int16 chunks.
Used by app pipeline, speech module server, and speech module internals.
"""

from __future__ import annotations

import logging
import struct

logger = logging.getLogger(__name__)

INT16_MAX = 32767


def chunk_rms_level(chunk: bytes | None) -> float:
    """
    Return RMS level of chunk (int16 little-endian) normalized to 0.0--1.0.
    Returns 0.0 for None, empty, or too short chunk; never raises.
    """
    if chunk is None or len(chunk) < 2:
        return 0.0
    try:
        n = len(chunk) // 2
        samples = struct.unpack(f"<{n}h", chunk)
        total = sum(s * s for s in samples)
        rms = (total / n) ** 0.5 if n else 0.0
        return min(1.0, rms / INT16_MAX)
    except (struct.error, ZeroDivisionError, ValueError) as e:
        logger.debug("chunk_rms_level failed: %s", e)
        return 0.0
