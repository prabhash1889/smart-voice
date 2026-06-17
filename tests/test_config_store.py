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
