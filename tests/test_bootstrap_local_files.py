from backend.bootstrap_local_files import ensure_local_templates


def test_ensure_local_templates_creates_missing_eon_files(tmp_path):
    (tmp_path / "eon_api.example.json").write_text("{}", encoding="utf-8")
    (tmp_path / "eon_channels.example.json").write_text("{}", encoding="utf-8")

    created = ensure_local_templates(tmp_path)

    assert "eon_api.json" in created
    assert "eon_channels.json" in created
    assert (tmp_path / "eon_api.json").exists()
    # Second run is idempotent
    assert ensure_local_templates(tmp_path) == []
