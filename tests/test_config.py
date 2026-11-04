from meridiano import config_base


def test_env_int_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("MERIDIAN_TEST_INT", raising=False)
    assert config_base._env_int("MERIDIAN_TEST_INT", 50) == 50


def test_env_int_defaults_when_empty(monkeypatch):
    monkeypatch.setenv("MERIDIAN_TEST_INT", "")
    assert config_base._env_int("MERIDIAN_TEST_INT", 50) == 50


def test_env_int_defaults_when_invalid(monkeypatch):
    monkeypatch.setenv("MERIDIAN_TEST_INT", "abc")
    assert config_base._env_int("MERIDIAN_TEST_INT", 50) == 50


def test_env_int_reads_value(monkeypatch):
    monkeypatch.setenv("MERIDIAN_TEST_INT", "7")
    assert config_base._env_int("MERIDIAN_TEST_INT", 50) == 7
