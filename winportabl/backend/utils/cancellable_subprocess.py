from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional
import threading


_cancel_event: ContextVar[Optional[threading.Event]] = ContextVar(
    "subprocess_cancel_event",
    default=None,
)


@contextmanager
def subprocess_cancel_scope(cancel_event: Optional[threading.Event]) -> Iterator[None]:
    token = _cancel_event.set(cancel_event)
    try:
        yield
    finally:
        _cancel_event.reset(token)


def _raise_cancelled() -> None:
    from backend.jobs.exceptions import JobCancelled

    raise JobCancelled("Download cancelled by user")


def raise_if_cancelled(cancel_event: Optional[threading.Event] = None) -> None:
    event = cancel_event if cancel_event is not None else _cancel_event.get()
    if event and event.is_set():
        _raise_cancelled()


def current_cancel_event() -> Optional[threading.Event]:
    return _cancel_event.get()


def _stop_process(proc: subprocess.Popen, grace_seconds: float = 3.0) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=grace_seconds)
    except Exception:
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=grace_seconds)
            except Exception:
                pass


def run(*popenargs, cancel_event: Optional[threading.Event] = None, poll_interval: float = 0.25, **kwargs):
    """subprocess.run replacement that terminates the child when the active job is cancelled."""
    event = cancel_event if cancel_event is not None else _cancel_event.get()
    if event is None:
        return subprocess.run(*popenargs, **kwargs)
    raise_if_cancelled(event)

    if kwargs.get("input") is not None:
        return subprocess.run(*popenargs, **kwargs)

    timeout = kwargs.pop("timeout", None)
    check = kwargs.pop("check", False)
    capture_output = kwargs.pop("capture_output", False)
    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    proc = subprocess.Popen(*popenargs, **kwargs)
    started = time.monotonic()
    stdout = stderr = None

    try:
        while True:
            if event.is_set():
                _stop_process(proc)
                raise_if_cancelled(event)

            step = poll_interval
            if timeout is not None:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    _stop_process(proc, grace_seconds=0.5)
                    raise subprocess.TimeoutExpired(proc.args, timeout, output=stdout, stderr=stderr)
                step = min(step, remaining)

            try:
                stdout, stderr = proc.communicate(timeout=step)
                break
            except subprocess.TimeoutExpired:
                continue
    except Exception:
        if proc.poll() is None:
            _stop_process(proc, grace_seconds=0.5)
        raise

    result = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    if check and result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result
