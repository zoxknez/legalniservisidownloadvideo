"""CENC decrypt helpers (mp4decrypt)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from backend.utils.cancellable_subprocess import run as run_subprocess

logger = logging.getLogger("pipeline.decrypt")


def decrypt_cenc(
    encrypted: Path,
    keys: List[str],
    mp4decrypt: str,
    *,
    output: Optional[Path] = None,
) -> Path:
    """
    Decrypt an encrypted ISOBMFF file with Bento4 mp4decrypt.

    keys: list of "kid:key" hex pairs.
    """
    encrypted = Path(encrypted)
    if not encrypted.is_file():
        raise FileNotFoundError(f"Encrypted file missing: {encrypted}")
    if not keys:
        raise ValueError("No CONTENT keys for decryption")

    if output is None:
        stem = encrypted.stem.replace("_enc", "_dec")
        if stem == encrypted.stem:
            stem = encrypted.stem + "_dec"
        output = encrypted.with_name(stem + encrypted.suffix)

    output = Path(output)
    if output.exists() and output.stat().st_size > 1024:
        # Resume: already decrypted
        logger.info("[decrypt] skip existing %s", output.name)
        return output

    cmd = [mp4decrypt]
    for key in keys:
        cmd += ["--key", key]
    cmd += [str(encrypted), str(output)]

    logger.info("[decrypt] %s → %s (%s key(s))", encrypted.name, output.name, len(keys))
    result = run_subprocess(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"mp4decrypt failed: {err[-500:]}")
    return output
