import os

from smartvoice.storage.config_store import ConfigStore


def test_config_merges_user_values(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"hotkeys": {"push_to_talk": "ctrl+shift+space"}}', encoding="utf-8")

    config = ConfigStore(config_path=path).load()

    assert config["hotkeys"]["push_to_talk"] == "ctrl+shift+space"
    assert config["audio"]["sample_rate"] == 16000


def test_config_expands_old_mode_list(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"modes": {"available": ["raw_transcript"]}}', encoding="utf-8")

    config = ConfigStore(config_path=path).load()

    assert "raw_transcript" in config["modes"]["available"]
    assert "commit_message" in config["modes"]["available"]


def test_config_save_falls_back_when_config_file_is_not_writable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    blocked_path = tmp_path / "blocked" / "config.json"
    store = ConfigStore(config_path=blocked_path)
    original_open = type(blocked_path).open

    def fake_open(path, *args, **kwargs):
        if path == blocked_path and "w" in args[0]:
            raise PermissionError("blocked")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(type(blocked_path), "open", fake_open)

    store.save({"audio": {"input_device_id": 27}})

    assert (tmp_path / ".smartvoice" / "config.json").exists()


def test_config_load_prefers_newer_fallback_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    primary_path = tmp_path / "primary" / "config.json"
    primary_path.parent.mkdir()
    primary_path.write_text('{"audio": {"input_device_id": 15}}', encoding="utf-8")
    fallback_path = tmp_path / ".smartvoice" / "config.json"
    fallback_path.parent.mkdir()
    fallback_path.write_text('{"audio": {"input_device_id": 27}}', encoding="utf-8")
    os.utime(fallback_path, (primary_path.stat().st_mtime + 10, primary_path.stat().st_mtime + 10))

    config = ConfigStore(config_path=primary_path).load()

    assert config["audio"]["input_device_id"] == 27
