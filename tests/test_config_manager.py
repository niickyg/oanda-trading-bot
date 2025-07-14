

import json
import time
from pathlib import Path

import pytest
import os

# Adjust import to your module path if needed
from config_manager import ConfigManager, CONFIG_PATH

@pytest.fixture(autouse=True)
def isolate_tmp(tmp_path, monkeypatch):
    # Ensure each test runs in its own temp dir
    monkeypatch.chdir(tmp_path)
    yield

def write_config(data):
    # Helper to write JSON to the config file path
    Path(CONFIG_PATH).write_text(json.dumps(data))

def test_initial_load_and_callback(monkeypatch):
    # Write initial config
    initial = {"foo": 123}
    write_config(initial)

    seen = []
    cm = ConfigManager(on_update=seen.append, poll_interval=0.05)
    cm.start()
    # Allow time for initial callback
    time.sleep(0.1)
    cm.stop()

    assert seen == [initial]

@pytest.mark.skipif(os.getenv("CI"), reason="FS events unreliable on CI")
def test_hot_reload_triggers_callback(monkeypatch):
    # Write initial config
    write_config({"step": 1})
    seen = []
    cm = ConfigManager(on_update=seen.append, poll_interval=0.05)
    cm.start()
    time.sleep(0.1)

    # Update config file
    write_config({"step": 2})
    time.sleep(0.1)
    cm.stop()

    assert seen == [{"step": 1}, {"step": 2}]

def test_no_callback_if_no_change(monkeypatch):
    write_config({"value": 10})
    seen = []
    cm = ConfigManager(on_update=seen.append, poll_interval=0.05)
    cm.start()
    time.sleep(0.1)
    # Overwrite with identical content
    write_config({"value": 10})
    time.sleep(0.1)
    cm.stop()

    # Only initial callback, no duplicate on unchanged
    assert seen == [{"value": 10}]