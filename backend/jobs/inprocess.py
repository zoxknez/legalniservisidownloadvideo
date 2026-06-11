"""
In-process download jobs for the queue (no subprocess for supported services).
"""
from __future__ import annotations

import json
import logging
import re
import sys
from contextlib import contextmanager
from io import StringIO
from typing import Any, Callable, Dict, List, Optional
import threading

from backend.config import config
from backend.utils.cancellable_subprocess import subprocess_cancel_scope

INPROCESS_MARKER = "@inprocess"
LogFn = Callable[[str], None]

logger = logging.getLogger(__name__)


def build_job(service: str, action: str, params: Optional[Dict[str, Any]] = None) -> List[str]:
    payload = {"service": service, "action": action, "params": params or {}}
    return [INPROCESS_MARKER, json.dumps(payload, ensure_ascii=False)]


def is_inprocess_job(cmd: List[str]) -> bool:
    return bool(cmd) and cmd[0] == INPROCESS_MARKER and len(cmd) >= 2


def parse_job(cmd: List[str]) -> Dict[str, Any]:
    if not is_inprocess_job(cmd):
        raise ValueError("Not an in-process job command")
    return json.loads(cmd[1])


class _QueueLogHandler(logging.Handler):
    def __init__(self, emit_fn: LogFn):
        super().__init__()
        self._emit_fn = emit_fn

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if msg:
                self._emit_fn(msg)
        except Exception:
            pass


@contextmanager
def capture_job_output(log_fn: LogFn, logger_names: Optional[List[str]] = None):
    """Capture logging + stdout/stderr into queue log lines."""
    handler = _QueueLogHandler(log_fn)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

    attached: List[logging.Logger] = []
    names = logger_names or ["", "VoyoDownloader", "backend", "HBOMaxDownloader"]
    for name in names:
        lg = logging.getLogger(name) if name else logging.getLogger()
        lg.addHandler(handler)
        attached.append(lg)

    old_stdout, old_stderr = sys.stdout, sys.stderr
    stream = _StreamProxy(log_fn, old_stdout)
    sys.stdout = stream
    sys.stderr = stream
    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        for lg in attached:
            lg.removeHandler(handler)


class _StreamProxy:
    def __init__(self, log_fn: LogFn, fallback):
        self._log_fn = log_fn
        self._fallback = fallback
        self._buf = ""

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                self._log_fn(line)
        return len(data)

    def flush(self) -> None:
        if self._buf.strip():
            self._log_fn(self._buf.rstrip())
            self._buf = ""
        if hasattr(self._fallback, "flush"):
            self._fallback.flush()


def execute_job(
    payload: Dict[str, Any],
    log_fn: LogFn,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    service = payload.get("service", "")
    action = payload.get("action", "")
    params = payload.get("params") or {}

    with subprocess_cancel_scope(cancel_event):
        if service == "voyo":
            from backend.jobs.voyo_job import run_voyo_job
            return run_voyo_job(action, params, log_fn, cancel_event)
        if service in ("hbomax", "hbo"):
            from backend.jobs.hbo_job import run_hbo_job
            return run_hbo_job(action, params, log_fn, cancel_event)
        if service == "sniffer":
            from backend.jobs.sniffer_job import run_sniffer_job
            return run_sniffer_job(action, params, log_fn, cancel_event)
        if service == "hrti":
            from backend.jobs.hrti_job import run_hrti_job
            return run_hrti_job(action, params, log_fn, cancel_event)
        if service == "rtsplaneta":
            from backend.jobs.rts_job import run_rts_job
            return run_rts_job(action, params, log_fn, cancel_event)
        if service == "eon":
            from backend.jobs.eon_job import run_eon_job
            return run_eon_job(action, params, log_fn, cancel_event)

    log_fn(f"ERROR Nepoznat in-process servis: {service}")
    return False


def get_output_dir_from_cmd(cmd: List[str]) -> Optional[str]:
    if is_inprocess_job(cmd):
        try:
            params = parse_job(cmd).get("params") or {}
            return params.get("output_dir")
        except Exception:
            return None
    for idx, part in enumerate(cmd):
        if part == "-o" and idx + 1 < len(cmd):
            return cmd[idx + 1]
    return None
