import os
from scripts.env_loader import load_skill_env


def test_load_skill_env_reads_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nDEEPSEEK_API_KEY=sk-test123\nDEEPSEEK_MODEL=deepseek-v4-flash\n\n",
                   encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    loaded = load_skill_env(env)
    assert loaded["DEEPSEEK_API_KEY"] == "sk-test123"
    assert os.environ["DEEPSEEK_API_KEY"] == "sk-test123"
    assert os.environ["DEEPSEEK_MODEL"] == "deepseek-v4-flash"


def test_load_skill_env_does_not_override_existing(tmp_path, monkeypatch):
    # 系统 env 已设的键优先，.env 不覆盖
    env = tmp_path / ".env"
    env.write_text("DEEPSEEK_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "from-system")
    loaded = load_skill_env(env)
    assert "DEEPSEEK_API_KEY" not in loaded
    assert os.environ["DEEPSEEK_API_KEY"] == "from-system"


def test_load_skill_env_missing_file_returns_empty(tmp_path):
    assert load_skill_env(tmp_path / "nonexistent.env") == {}


def test_load_skill_env_strips_quotes(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('KEY="quoted value"\n', encoding="utf-8")
    monkeypatch.delenv("KEY", raising=False)
    load_skill_env(env)
    assert os.environ["KEY"] == "quoted value"
