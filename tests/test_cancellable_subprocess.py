from __future__ import annotations

import sys
import threading
import time

import pytest

from backend.jobs.exceptions import JobCancelled
from backend.utils.cancellable_subprocess import run, subprocess_cancel_scope


def test_cancellable_subprocess_stops_when_event_is_set():
    cancel_event = threading.Event()
    timer = threading.Timer(0.2, cancel_event.set)
    started = time.monotonic()
    timer.start()
    try:
        with pytest.raises(JobCancelled):
            run(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                cancel_event=cancel_event,
                poll_interval=0.05,
                capture_output=True,
                text=True,
            )
    finally:
        timer.cancel()

    assert time.monotonic() - started < 3


def test_cancellable_subprocess_uses_active_scope():
    cancel_event = threading.Event()
    cancel_event.set()

    with subprocess_cancel_scope(cancel_event), pytest.raises(JobCancelled):
        run([sys.executable, "-c", "print('should not run')"])
