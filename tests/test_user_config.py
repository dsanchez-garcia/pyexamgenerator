"""Tests for the per-user configuration: location, legacy fallback/migration and preserved keys."""
import json
import os
import stat
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

from pyexamgenerator import user_config
from pyexamgenerator.user_config import (
    get_ai_config_path,
    get_legacy_ai_config_path,
    get_user_config_dir,
    merge_ai_config,
    parse_ai_config,
    read_ai_config_file,
    save_ai_config,
)


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture
def config_env(tmp_path, monkeypatch):
    """Per-user folder (through APPDATA, as on Windows) and a working folder, both inside tmp_path."""
    appdata = tmp_path / "AppData" / "Roaming"
    work = tmp_path / "curso_sincronizado"
    work.mkdir()
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.chdir(work)
    user_dir = appdata / "pyexamgenerator"
    return SimpleNamespace(user_dir=user_dir, user_file=user_dir / "config.json",
                           legacy_file=Path(os.getcwd()) / "config.json")


# ---------------------------------------------------------------------------
# Location of the per-user folder
# ---------------------------------------------------------------------------
def test_per_user_folder_is_under_appdata_on_windows(config_env):
    assert Path(get_user_config_dir()) == config_env.user_dir
    assert Path(get_ai_config_path()) == config_env.user_file
    assert Path(get_legacy_ai_config_path()) == config_env.legacy_file
    assert not config_env.user_dir.exists()  # it is only created when something is saved


def test_per_user_folder_is_under_dot_config_elsewhere(tmp_path, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # home folder of os.path.expanduser on Windows

    assert Path(get_user_config_dir()) == tmp_path / ".config" / "pyexamgenerator"
    assert Path(get_ai_config_path()) == tmp_path / ".config" / "pyexamgenerator" / "config.json"


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
def test_save_writes_the_per_user_file_and_nothing_in_the_working_folder(config_env):
    saved = save_ai_config({"provider": "openai", "api_keys": {"openai": "sk-uno"},
                            "models": {"openai": "gpt-6-luna"}})

    assert Path(saved) == config_env.user_file
    assert _read_json(saved) == {"provider": "openai", "api_keys": {"openai": "sk-uno"},
                                 "models": {"openai": "gpt-6-luna"}}
    assert not config_env.legacy_file.exists()
    assert list(config_env.user_dir.iterdir()) == [config_env.user_file]  # no temporary file is left


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_saved_file_is_readable_only_by_the_user(config_env):
    ai_config = {"provider": "gemini", "api_keys": {"gemini": "AIza-uno"}, "models": {}}

    saved = save_ai_config(ai_config)
    assert stat.S_IMODE(os.stat(saved).st_mode) == 0o600

    os.chmod(saved, 0o644)  # e.g. a file replaced by hand
    save_ai_config(ai_config)
    assert stat.S_IMODE(os.stat(saved).st_mode) == 0o600


def test_failed_save_keeps_the_previous_file(config_env, monkeypatch):
    previous = {"provider": "gemini", "api_keys": {"gemini": "AIza-uno", "mistral": "ms-uno"}}
    _write_json(config_env.user_file, previous)

    def dump_and_fail(data, f, **kwargs):
        f.write('{"provider": "gem')
        raise OSError("No queda espacio en el disco")

    monkeypatch.setattr(user_config.json, "dump", dump_and_fail)
    with pytest.raises(OSError):
        save_ai_config({"provider": "openai", "api_keys": {"openai": "sk-uno"}, "models": {}})

    assert _read_json(config_env.user_file) == previous
    assert list(config_env.user_dir.iterdir()) == [config_env.user_file]


def test_save_never_falls_back_to_the_working_folder(config_env, tmp_path, monkeypatch):
    not_a_folder = tmp_path / "no_es_una_carpeta"
    not_a_folder.write_text("x", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(not_a_folder))  # the per-user folder cannot be created

    with pytest.raises(OSError):
        save_ai_config({"provider": "gemini", "api_keys": {"gemini": "AIza-uno"}, "models": {}})

    assert not config_env.legacy_file.exists()


# ---------------------------------------------------------------------------
# Reading: the per-user file first, then the legacy file of the working folder
# ---------------------------------------------------------------------------
def test_per_user_file_is_read_before_the_legacy_one(config_env):
    _write_json(config_env.user_file, {"provider": "anthropic", "api_keys": {"anthropic": "sk-ant-usuario"}})
    _write_json(config_env.legacy_file, {"api_key": "AIza-carpeta"})

    config, path = read_ai_config_file()

    assert Path(path) == config_env.user_file
    assert parse_ai_config(config) == {"provider": "anthropic", "api_keys": {"anthropic": "sk-ant-usuario"},
                                       "models": {}}


def test_legacy_file_is_read_while_there_is_no_per_user_file(config_env):
    _write_json(config_env.legacy_file, {"api_key": "AIza-antigua"})

    config, path = read_ai_config_file()

    assert Path(path) == config_env.legacy_file
    assert parse_ai_config(config)["api_keys"] == {"gemini": "AIza-antigua"}


def test_unreadable_per_user_file_falls_back_to_the_legacy_one(config_env):
    config_env.user_dir.mkdir(parents=True)
    config_env.user_file.write_text('{"api_keys": {"gemini": ', encoding="utf-8")  # cut file
    _write_json(config_env.legacy_file, {"api_key": "AIza-antigua"})

    assert Path(read_ai_config_file()[1]) == config_env.legacy_file


def test_without_files_the_configuration_is_empty(config_env):
    config, path = read_ai_config_file()

    assert (config, path) == ({}, None)
    assert parse_ai_config(config) == {"provider": "gemini", "api_keys": {}, "models": {}}


def test_legacy_api_key_is_read_as_the_gemini_key():
    assert parse_ai_config({"api_key": "AIza-antigua"})["api_keys"] == {"gemini": "AIza-antigua"}
    # The per-provider key wins over the legacy field.
    parsed = parse_ai_config({"api_key": "AIza-antigua", "api_keys": {"gemini": "AIza-nueva"}})
    assert parsed["api_keys"] == {"gemini": "AIza-nueva"}
    # The application only uses known providers and valid keys (the file keeps the rest).
    parsed = parse_ai_config({"provider": "mistral", "api_keys": {"mistral": "ms-uno", "openai": "TU_CLAVE_API"},
                              "models": {"mistral": "mistral-large", "openai": " "}})
    assert parsed == {"provider": "gemini", "api_keys": {}, "models": {}}


# ---------------------------------------------------------------------------
# Migration and preserved content
# ---------------------------------------------------------------------------
def test_first_save_migrates_the_legacy_file_without_deleting_it(config_env):
    _write_json(config_env.legacy_file, {
        "provider": "gemini",
        "api_key": "AIza-antigua",
        "api_keys": {"gemini": "AIza-antigua", "mistral": "ms-uno"},
        "models": {"gemini": "gemini-flash-latest", "mistral": "mistral-large"},
        "otro_ajuste": True,
    })
    legacy_bytes = config_env.legacy_file.read_bytes()

    ai_config = parse_ai_config(read_ai_config_file()[0])
    ai_config["api_keys"]["openai"] = "sk-nueva"
    ai_config["models"]["openai"] = "gpt-6-luna"
    ai_config["provider"] = "openai"
    save_ai_config(ai_config)

    assert _read_json(config_env.user_file) == {
        "provider": "openai",
        "api_key": "AIza-antigua",
        "api_keys": {"gemini": "AIza-antigua", "mistral": "ms-uno", "openai": "sk-nueva"},
        "models": {"gemini": "gemini-flash-latest", "mistral": "mistral-large", "openai": "gpt-6-luna"},
        "otro_ajuste": True,
    }
    assert config_env.legacy_file.read_bytes() == legacy_bytes  # neither modified nor deleted
    assert Path(read_ai_config_file()[1]) == config_env.user_file  # from now on, the per-user file is read


def test_save_keeps_unknown_providers_and_other_settings_of_the_per_user_file(config_env):
    _write_json(config_env.user_file, {
        "provider": "gemini",
        "api_keys": {"gemini": "AIza-uno", "mistral": "ms-uno"},
        "models": {"mistral": "mistral-large"},
        "otro_ajuste": [1, 2],
    })
    _write_json(config_env.legacy_file, {"api_key": "AIza-carpeta", "api_keys": {"deepseek": "ds-carpeta"}})

    ai_config = parse_ai_config(read_ai_config_file()[0])
    ai_config["api_keys"]["gemini"] = "AIza-dos"
    save_ai_config(ai_config)

    saved = _read_json(config_env.user_file)
    assert saved["api_keys"] == {"gemini": "AIza-dos", "mistral": "ms-uno"}  # nothing from the legacy file
    assert saved["models"] == {"mistral": "mistral-large"}
    assert saved["otro_ajuste"] == [1, 2]
    assert saved["api_key"] == "AIza-dos"  # the legacy field follows the Gemini key


def test_parse_and_merge_do_not_modify_their_arguments():
    config = {"api_key": "AIza-antigua", "api_keys": {"mistral": "ms-uno"}, "models": {}}
    ai_config = {"provider": "gemini", "api_keys": {"gemini": "AIza-nueva"}, "models": {}}

    parse_ai_config(config)
    merged = merge_ai_config(config, ai_config)

    assert merged["api_keys"] == {"mistral": "ms-uno", "gemini": "AIza-nueva"}
    assert config == {"api_key": "AIza-antigua", "api_keys": {"mistral": "ms-uno"}, "models": {}}
    assert ai_config == {"provider": "gemini", "api_keys": {"gemini": "AIza-nueva"}, "models": {}}


# ---------------------------------------------------------------------------
# GUI wiring: needs tkinter, but no window is created
# ---------------------------------------------------------------------------
class _Var:
    """Minimal stand-in for tk.StringVar (get/set), so that no window is created."""

    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


@pytest.fixture
def gui(config_env, monkeypatch):
    pytest.importorskip("tkinter")
    from pyexamgenerator import main_app

    shown = []
    monkeypatch.setattr(main_app.messagebox, "showinfo", lambda title, message, **kw: shown.append(("info", message)))
    monkeypatch.setattr(main_app.messagebox, "showerror", lambda title, message, **kw: shown.append(("error", message)))

    def make_app():
        app = SimpleNamespace(api_key_var=_Var(), selected_model_var=_Var(), ai_provider_var=_Var("gemini"),
                              api_key_info_var=_Var(), api_keys_by_provider={}, api_key_sources={})
        for name in ("load_ai_config", "_save_ai_config", "_ai_config_is_legacy", "_selected_provider",
                     "_refresh_provider_widgets", "save_api_key", "save_current_api_key"):
            setattr(app, name, MethodType(getattr(main_app.ExamApp, name), app))
        app.ai_config = app.load_ai_config()
        return app

    return SimpleNamespace(main_app=main_app, make_app=make_app, shown=shown, env=config_env)


def test_gui_saves_the_key_in_the_per_user_file_and_reports_the_migration(gui):
    env = gui.env
    _write_json(env.legacy_file, {"api_key": "AIza-antigua"})
    app = gui.make_app()
    app.api_key_sources["gemini"] = "config"  # as ExamApp.__init__ does for a key read from the file
    app._refresh_provider_widgets()
    assert str(env.legacy_file) in app.api_key_info_var.get()  # the key comes from the old location

    app.ai_provider_var.set("openai")
    app.api_key_var.set("sk-nueva")
    app.selected_model_var.set("gpt-6-luna")
    app.save_current_api_key()

    kind, message = gui.shown[-1]
    assert kind == "info" and str(env.user_file) in message and str(env.legacy_file) in message
    assert _read_json(env.user_file)["api_keys"] == {"gemini": "AIza-antigua", "openai": "sk-nueva"}
    assert _read_json(env.legacy_file) == {"api_key": "AIza-antigua"}
    assert str(env.user_file) in app.api_key_info_var.get()

    app.save_current_api_key()  # nothing left to migrate
    assert str(env.legacy_file) not in gui.shown[-1][1]


def test_gui_reports_the_path_when_the_per_user_file_cannot_be_written(gui, tmp_path, monkeypatch):
    not_a_folder = tmp_path / "no_es_una_carpeta"
    not_a_folder.write_text("x", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(not_a_folder))
    app = gui.make_app()
    app.api_key_var.set("AIza-uno")

    app.save_current_api_key()

    kind, message = gui.shown[-1]
    assert kind == "error" and os.path.join(str(not_a_folder), "pyexamgenerator", "config.json") in message
    assert not gui.env.legacy_file.exists()


def test_exam_template_fallback_uses_the_same_per_user_folder(gui):
    local_path, central_path = gui.main_app.ExamApp._get_exam_template_config_paths()

    assert Path(local_path) == gui.env.legacy_file.with_name("exam_generation_template.json")
    assert Path(central_path) == gui.env.user_dir / "exam_generation_template.json"
