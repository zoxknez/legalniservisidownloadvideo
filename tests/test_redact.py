from backend.queue_manager import redact_command, redact_log_line


def test_redact_command_masks_password_flag():
    cmd = ["python", "script.py", "-p", "secret123", "--url", "https://x"]
    assert "secret123" not in redact_command(cmd)
    assert "***" in redact_command(cmd)


def test_redact_log_line_masks_token_query():
    line = "GET /stream?access_token=supersecretvalue&foo=bar"
    out = redact_log_line(line)
    assert "supersecretvalue" not in out
    assert "access_token=***" in out
